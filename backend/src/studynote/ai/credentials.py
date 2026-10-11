"""System credentials with one-time migration from the previous DPAPI file."""
import hashlib
import os
from pathlib import Path

from .legacy_dpapi import _crypt
from .windows_credentials import MAX_CREDENTIAL_BYTES, WindowsCredentialBackend


class KeyStore:
    def __init__(self, directory: Path, backend=None):
        directory = Path(directory).resolve()
        # A backup restored elsewhere must not silently reuse another workspace's key.
        identity = os.path.normcase(str(directory)).encode("utf-8")
        self.target = "StudyNote/" + hashlib.sha256(identity).hexdigest()[:32] + "/api-key"
        self.path = directory / "api-key.dpapi"  # Legacy migration source only.
        self.backend = backend or WindowsCredentialBackend()

    @staticmethod
    def _validate(key):
        key = key.strip()
        if not key or any(character.isspace() for character in key):
            raise ValueError("API Key 不能为空或包含空白字符。")
        if len(key.encode("utf-8")) > MAX_CREDENTIAL_BYTES:
            raise ValueError("API Key 超过系统凭据长度限制。")
        return key

    def is_configured(self):
        return self.backend.read(self.target) is not None or self.path.exists()

    def save(self, key: str):
        key = self._validate(key)
        self.backend.write(self.target, key.encode("utf-8"))
        # Remove a legacy file only after the system write succeeded.
        self.path.unlink(missing_ok=True)

    def load(self) -> str:
        secret = self.backend.read(self.target)
        if secret is not None:
            try:
                return self._validate(secret.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                raise RuntimeError("系统凭据无效，请重新配置 API Key。") from None
        if not self.path.exists():
            raise ValueError("请先在 AI 设置中保存 API Key。")
        try:
            key = self._validate(_crypt(self.path.read_bytes(), decrypt=True).decode("utf-8"))
        except (RuntimeError, UnicodeDecodeError, ValueError):
            raise RuntimeError("旧版凭据无法迁移，请在当前 Windows 账号重新配置 API Key。") from None
        self.save(key)
        return key

    def delete(self):
        self.backend.delete(self.target)
        self.path.unlink(missing_ok=True)
