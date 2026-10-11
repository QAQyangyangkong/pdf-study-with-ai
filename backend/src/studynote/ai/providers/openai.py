import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

class APIError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward a bearer key through redirects.


def http_transport(base_url, key, payload):
    request = Request(base_url.rstrip("/") + "/chat/completions",
                      data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                      headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with build_opener(NoRedirect()).open(request, timeout=60) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise APIError("模型响应过大，请降低输出长度。")
            return json.loads(raw)
    except HTTPError as error:
        messages = {400: "模型或参数不兼容，请检查模型名称。", 401: "API Key 无效，请重新配置。",
                    402: "服务商余额不足。", 403: "当前密钥没有调用权限。",
                    404: "接口或模型不存在，请检查 API 地址和模型名称。",
                    429: "请求过于频繁，请稍后手动重试。"}
        message = messages.get(error.code, "服务商暂时无法响应，请稍后重试。")
        error.close()
        raise APIError(message) from None
    except (URLError, TimeoutError, OSError):
        raise APIError("连接失败或超时，请检查网络；未自动重试，避免重复扣费。") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise APIError("服务商未返回兼容的 JSON 响应。") from None
