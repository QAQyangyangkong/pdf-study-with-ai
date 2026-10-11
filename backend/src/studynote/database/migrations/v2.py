"""Upgrade the first prototype without changing document IDs or file paths."""
from datetime import datetime
import sqlite3

SQL = """
BEGIN IMMEDIATE;
CREATE TABLE note_versions (
 id INTEGER PRIMARY KEY, note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
 title TEXT NOT NULL, body TEXT NOT NULL, sources TEXT NOT NULL,
 created_at TEXT NOT NULL);
INSERT INTO note_versions(note_id,title,body,sources,created_at)
 SELECT id,title,body,sources,updated_at FROM notes;
PRAGMA user_version=2;
COMMIT;
"""


def apply(connection):
    """Apply v2 inside the caller's migration transaction."""
    connection.execute("""CREATE TABLE note_versions (
      id INTEGER PRIMARY KEY, note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
      title TEXT NOT NULL, body TEXT NOT NULL, sources TEXT NOT NULL,
      created_at TEXT NOT NULL)""")
    connection.execute(
        "INSERT INTO note_versions(note_id,title,body,sources,created_at) "
        "SELECT id,title,body,sources,updated_at FROM notes")


def upgrade(path):
    backups = path.parent / "backups"
    backups.mkdir(exist_ok=True)
    destination = backups / ("schema-v1-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".sqlite3")
    source, target = sqlite3.connect(path), sqlite3.connect(destination)
    try:
        source.backup(target)
    finally:
        source.close()
        target.close()
    connection = sqlite3.connect(path)
    try:
        connection.executescript(SQL)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return destination
