"""Back up older databases, then atomically add the local full-text index.

The trigram tokenizer indexes literal Chinese and English substrings without
requiring a dictionary. Triggers keep the external-content index consistent.
See https://www.sqlite.org/fts5.html#the_trigram_tokenizer and
https://www.sqlite.org/fts5.html#external_content_tables .
"""
from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3

from .v2 import apply as apply_v2


STATEMENTS = (
    "CREATE VIRTUAL TABLE notes_fts USING fts5("
    "title, body, content='notes', content_rowid='id', tokenize='trigram')",
    """CREATE TRIGGER notes_fts_insert AFTER INSERT ON notes BEGIN
      INSERT INTO notes_fts(rowid,title,body) VALUES(new.id,new.title,new.body);
    END""",
    """CREATE TRIGGER notes_fts_update AFTER UPDATE OF title,body ON notes BEGIN
      INSERT INTO notes_fts(notes_fts,rowid,title,body)
        VALUES('delete',old.id,old.title,old.body);
      INSERT INTO notes_fts(rowid,title,body) VALUES(new.id,new.title,new.body);
    END""",
    """CREATE TRIGGER notes_fts_delete AFTER DELETE ON notes BEGIN
      INSERT INTO notes_fts(notes_fts,rowid,title,body)
        VALUES('delete',old.id,old.title,old.body);
    END""",
    "INSERT INTO notes_fts(notes_fts) VALUES('rebuild')",
)


def apply(connection):
    """Build/rebuild the index within the caller's transaction."""
    for statement in STATEMENTS:
        connection.execute(statement)


def _backup(path, version):
    backups = path.parent / "backups"
    backups.mkdir(exist_ok=True)
    destination = backups / (
        f"schema-v{version}-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".sqlite3")
    # Read from another connection: backing up the connection holding the write
    # transaction itself would wait for that transaction to finish indefinitely.
    with closing(sqlite3.connect(path)) as source, closing(sqlite3.connect(destination)) as target:
        source.backup(target)
    return destination


def upgrade(path):
    """Upgrade v1/v2 in one transaction; preserve one pre-upgrade backup."""
    path = Path(path)
    with closing(sqlite3.connect(path, timeout=20)) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            connection.execute("BEGIN IMMEDIATE")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version == 3:
                connection.commit()
                return None
            if version not in (1, 2):
                raise ValueError("仅支持升级第 1 或第 2 版数据库。")
            destination = _backup(path, version)
            if version == 1:
                apply_v2(connection)
            apply(connection)
            connection.execute("PRAGMA user_version=3")
            connection.commit()
            return destination
        except Exception:
            connection.rollback()
            raise
