"""Current-user Windows Credential Manager, accessed through the Win32 API."""
import ctypes
import os
from ctypes import wintypes

CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
ERROR_NOT_FOUND = 1168
MAX_CREDENTIAL_BYTES = 2560


class Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(wintypes.BYTE)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


class WindowsCredentialBackend:
    def _api(self):
        if os.name != "nt":
            raise RuntimeError("系统凭据保存目前仅支持 Windows。")
        api = ctypes.WinDLL("advapi32", use_last_error=True)
        api.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
        api.CredWriteW.restype = wintypes.BOOL
        api.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                 ctypes.POINTER(ctypes.POINTER(Credential))]
        api.CredReadW.restype = wintypes.BOOL
        api.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        api.CredDeleteW.restype = wintypes.BOOL
        api.CredFree.argtypes = [ctypes.c_void_p]
        api.CredFree.restype = None
        return api

    def read(self, target):
        api = self._api()
        result = ctypes.POINTER(Credential)()
        if not api.CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(result)):
            if ctypes.get_last_error() == ERROR_NOT_FOUND:
                return None
            raise RuntimeError("Windows 无法读取系统凭据，请在当前账号重新配置。")
        try:
            credential = result.contents
            return ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
        finally:
            api.CredFree(result)

    def write(self, target, secret):
        if len(secret) > MAX_CREDENTIAL_BYTES:
            raise ValueError("API Key 超过系统凭据长度限制。")
        api = self._api()
        buffer = ctypes.create_string_buffer(secret)
        credential = Credential(
            Type=CRED_TYPE_GENERIC, TargetName=target,
            Comment="StudyNote API credential", UserName="StudyNote",
            CredentialBlobSize=len(secret),
            CredentialBlob=ctypes.cast(buffer, ctypes.POINTER(wintypes.BYTE)),
            Persist=CRED_PERSIST_LOCAL_MACHINE,
        )
        if not api.CredWriteW(ctypes.byref(credential), 0):
            raise RuntimeError("Windows 无法保存系统凭据，请检查当前账号权限。")

    def delete(self, target):
        api = self._api()
        if not api.CredDeleteW(target, CRED_TYPE_GENERIC, 0):
            if ctypes.get_last_error() != ERROR_NOT_FOUND:
                raise RuntimeError("Windows 无法删除系统凭据，请稍后再试。")
