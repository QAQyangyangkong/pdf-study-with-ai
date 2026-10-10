"""Application composition and consistent local backups."""
import tempfile
import zipfile
from pathlib import Path

from .ai import AIService
from .config import AIConfig
from .db import Database
from .documents import DocumentService
from .security import KeyStore


class Workspace:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.db = Database(self.directory / "study.sqlite3")
        self.documents = DocumentService(self.db, self.directory)
        self.keys = KeyStore(self.directory)
        self.ai = AIService(self.db, self.keys)

    def config(self):
        return AIConfig(**self.db.setting("ai", {})).validate()

    def backup(self, destination):
        destination = Path(destination)
        if destination.resolve().is_relative_to(self.directory.resolve()):
            raise ValueError("请将备份保存在工作区数据目录之外。")
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        try:
            with tempfile.TemporaryDirectory() as staging:
                snapshot = Path(staging) / "study.sqlite3"
                self.db.backup(snapshot)
                with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
                    archive.write(snapshot, "study.sqlite3")
                    for folder in ("documents", "chapters"):
                        for path in sorted((self.directory / folder).glob("*")):
                            if path.is_file() and path.suffix != ".tmp":
                                archive.write(path, path.relative_to(self.directory).as_posix())
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination
