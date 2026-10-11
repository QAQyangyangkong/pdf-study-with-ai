"""Versioned, allowlisted JSONL messages; no logging of request bodies."""
import json
from importlib.resources import files

MAX_REQUEST_BYTES = 512 * 1024


def contract():
    return json.loads(files("studynote.ipc").joinpath("protocol.schema.json").read_text(encoding="utf-8"))


def validate_request(request):
    if not isinstance(request, dict) or set(request) != {"protocol_version", "id", "method", "params"}:
        raise ValueError("请求格式不正确。")
    if type(request["protocol_version"]) is not int or request["protocol_version"] != 1:
        raise ValueError("前后端协议版本不兼容，请升级完整安装包。")
    if not isinstance(request["id"], str) or not 1 <= len(request["id"]) <= 80:
        raise ValueError("请求标识无效。")
    if request["method"] not in contract()["properties"]["method"]["enum"]:
        raise ValueError("未支持的操作。")
    if not isinstance(request["params"], dict) or len(request["params"]) > 20:
        raise ValueError("请求参数无效。")
    return request


def reply(request_id, result=None, error=None):
    response = {"protocol_version": 1, "id": request_id, "ok": error is None}
    if error is None:
        response["result"] = result
    else:
        response["error"] = {"code": "INVALID_REQUEST" if isinstance(error, ValueError) else "INTERNAL_ERROR",
                             "message": str(error) if isinstance(error, (ValueError, RuntimeError))
                             else "操作未完成，请检查文件和配置后重试。"}
    return response
