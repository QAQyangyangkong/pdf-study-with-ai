"""Windows DPAPI: no plaintext fallback and no key logging."""
import ctypes
import os
from ctypes import wintypes
from pathlib import Path


class Blob(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(value: bytes, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise RuntimeError("密钥安全保存目前仅支持 Windows。")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    buffer = ctypes.create_string_buffer(value)
    source = Blob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    function = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                         ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise RuntimeError("Windows 无法读取或保存密钥，请在当前账号重新配置。")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel32.LocalFree(ctypes.cast(target.data, ctypes.c_void_p))


class KeyStore:
    def __init__(self, directory: Path):
        self.path = directory / "api-key.dpapi"

    def save(self, key: str):
        key = key.strip()
        if not key or any(c.isspace() for c in key):
            raise ValueError("API Key 不能为空或包含空白字符。")
        encrypted = _crypt(key.encode("utf-8"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_bytes(encrypted)
        temporary.replace(self.path)

    def load(self) -> str:
        if not self.path.exists():
            raise ValueError("请先在 AI 设置中保存 API Key。")
        return _crypt(self.path.read_bytes(), decrypt=True).decode("utf-8")

    def delete(self):
        self.path.unlink(missing_ok=True)
