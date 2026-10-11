"""Packaged sidecar entry. JSONL production IPC; authenticated loopback dev bridge."""
import argparse
import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from .core.config import default_data_dir
from .core.workspace import Workspace
from .ipc.protocol import MAX_REQUEST_BYTES, reply
from .ipc.router import Router


def serve_stdio(router, source, output):
    while True:
        raw = source.readline(MAX_REQUEST_BYTES + 1)
        if not raw:
            return
        try:
            if len(raw.encode("utf-8")) > MAX_REQUEST_BYTES or not raw.endswith("\n"):
                raise ValueError("请求过大或缺少换行。")
            request = json.loads(raw)
            response = router.handle(request)
        except (ValueError, UnicodeDecodeError) as error:
            response = reply("",error=ValueError("请求不是有效的 JSONL 消息。"))
        output.write(json.dumps(response,ensure_ascii=False,separators=(",",":")) + "\n")
        output.flush()


def serve_http(router,port,token):
    if not token or len(token)<24:
        raise ValueError("开发桥接缺少临时授权令牌。")
    allowed_origin = "http://127.0.0.1:1420"
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass
        def headers_for(self,status):
            self.send_response(status)
            self.send_header("Content-Type","application/json; charset=utf-8")
            if self.headers.get("Origin") == allowed_origin:
                self.send_header("Access-Control-Allow-Origin",allowed_origin)
                self.send_header("Vary","Origin")
            self.end_headers()
        def do_OPTIONS(self):
            if self.headers.get("Origin") != allowed_origin:
                self.headers_for(403)
                return
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin",allowed_origin)
            self.send_header("Access-Control-Allow-Headers","Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods","POST, OPTIONS")
            self.end_headers()
        def do_POST(self):
            if (self.path != "/ipc" or self.headers.get("Origin",allowed_origin) != allowed_origin
                    or not hmac.compare_digest(self.headers.get("Authorization",""),"Bearer "+token)):
                self.headers_for(403)
                self.wfile.write(b'{"error":"forbidden"}')
                return
            try:
                size = int(self.headers.get("Content-Length","0"))
                if not 0 < size <= MAX_REQUEST_BYTES:
                    raise ValueError("请求过大或为空。")
                response = router.handle(json.loads(self.rfile.read(size).decode("utf-8")))
            except (ValueError,UnicodeDecodeError):
                response = reply("",error=ValueError("请求格式无效。"))
            self.headers_for(200)
            self.wfile.write(json.dumps(response,ensure_ascii=False).encode("utf-8"))
    server = HTTPServer(("127.0.0.1",port),Handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="StudyNote Python sidecar")
    parser.add_argument("--data-dir",type=Path)
    parser.add_argument("--http",type=int,help="Development-only loopback bridge port")
    parser.add_argument("--smoke-test",action="store_true")
    args = parser.parse_args()
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    override = os.environ.get("STUDYNOTE_DATA_DIR")
    router = Router(Workspace(args.data_dir or (Path(override) if override else default_data_dir())))
    try:
        if args.smoke_test:
            print(json.dumps(router.snapshot(),ensure_ascii=False))
        elif args.http:
            serve_http(router,args.http,os.environ.get("STUDYNOTE_DEV_TOKEN",""))
        else:
            serve_stdio(router,sys.stdin,sys.stdout)
    finally:
        router.close()


if __name__ == "__main__":
    main()
