"""SQLite persistence, migrations, request cache and budget reservations."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = 2
SCHEMA = """
CREATE TABLE documents (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, kind TEXT NOT NULL,
 course TEXT NOT NULL DEFAULT '', year TEXT NOT NULL DEFAULT '',
 digest TEXT NOT NULL, path TEXT NOT NULL, pages INTEGER NOT NULL,
 status TEXT NOT NULL, UNIQUE(digest, kind, course, year));
CREATE TABLE chapters (
 id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES documents(id),
 title TEXT NOT NULL, start_page INTEGER NOT NULL, end_page INTEGER NOT NULL,
 text TEXT NOT NULL, path TEXT NOT NULL);
CREATE TABLE notes (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
 sources TEXT NOT NULL DEFAULT '[]', kind TEXT NOT NULL DEFAULT 'note',
 updated_at TEXT NOT NULL);
CREATE TABLE topics (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE note_topics (
 note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
 topic_id INTEGER NOT NULL REFERENCES topics(id), PRIMARY KEY(note_id, topic_id));
CREATE TABLE settings (name TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE ai_cache (fingerprint TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE usage (
 id INTEGER PRIMARY KEY, day TEXT NOT NULL, model TEXT NOT NULL,
 amount REAL NOT NULL, status TEXT NOT NULL,
 input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0);
PRAGMA user_version = 1;
"""


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError("数据库由较新版本创建，请使用较新版本的软件。")
            if version == 0:
                # DDL and schema version form one transaction.
                connection.executescript("BEGIN IMMEDIATE;\n" + SCHEMA + "\nCOMMIT;")
        if version in (0, 1):
            from ..migrations.v2 import upgrade
            upgrade(self.path)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def rows(self, sql, values=()):
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(sql, values)]

    def execute(self, sql, values=()):
        with self.connect() as connection:
            return connection.execute(sql, values).lastrowid

    def get(self, table, item_id):
        if table not in {"documents", "chapters", "notes"}:
            raise ValueError("未知记录类型。")
        rows = self.rows(f"SELECT * FROM {table} WHERE id = ?", (item_id,))
        if not rows:
            raise ValueError("记录不存在，请刷新列表。")
        return rows[0]

    def setting(self, name, fallback=None):
        rows = self.rows("SELECT value FROM settings WHERE name = ?", (name,))
        return json.loads(rows[0]["value"]) if rows else fallback

    def set_setting(self, name, value):
        self.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)",
                     (name, json.dumps(value, ensure_ascii=False)))

    def save_note(self, title, body, sources=(), tags=(), kind="note", note_id=None):
        if not title.strip() or not body.strip():
            raise ValueError("笔记标题和正文不能为空。")
        now = datetime.now().isoformat(timespec="seconds")
        with self.connect() as connection:
            if note_id is None:
                note_id = connection.execute(
                    "INSERT INTO notes(title, body, sources, kind, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (title.strip(), body, json.dumps(list(sources), ensure_ascii=False), kind, now)
                ).lastrowid
            else:
                cursor = connection.execute(
                    "UPDATE notes SET title=?, body=?, updated_at=? WHERE id=?",
                    (title.strip(), body, now, note_id))
                if cursor.rowcount != 1:
                    raise ValueError("要保存的笔记不存在。")
            connection.execute("DELETE FROM note_topics WHERE note_id=?", (note_id,))
            for tag in sorted({tag.strip() for tag in tags if tag.strip()}):
                connection.execute("INSERT OR IGNORE INTO topics(name) VALUES (?)", (tag,))
                topic_id = connection.execute("SELECT id FROM topics WHERE name=?", (tag,)).fetchone()[0]
                connection.execute("INSERT INTO note_topics VALUES (?, ?)", (note_id, topic_id))
            connection.execute(
                "INSERT INTO note_versions(note_id,title,body,sources,created_at) "
                "SELECT id,title,body,sources,updated_at FROM notes WHERE id=?", (note_id,))
        return note_id

    def versions(self, note_id):
        return self.rows("SELECT * FROM note_versions WHERE note_id=? ORDER BY id DESC", (note_id,))

    def tags(self, note_id):
        return [row["name"] for row in self.rows(
            "SELECT t.name FROM topics t JOIN note_topics nt ON t.id=nt.topic_id "
            "WHERE nt.note_id=? ORDER BY t.name", (note_id,))]

    def notes(self, search="", topic=""):
        # Literal substring matching (not SQL wildcard interpretation).
        return self.rows(
            "SELECT DISTINCT n.* FROM notes n LEFT JOIN note_topics nt ON nt.note_id=n.id "
            "LEFT JOIN topics t ON t.id=nt.topic_id WHERE "
            "(?='' OR instr(n.title,?)>0 OR instr(n.body,?)>0) "
            "AND (?='' OR t.name=?) ORDER BY n.updated_at DESC, n.id DESC",
            (search, search, search, topic, topic))

    def spent(self, day=None):
        day = day or datetime.now().date().isoformat()
        return self.rows("SELECT COALESCE(SUM(amount),0) AS total FROM usage WHERE day=?", (day,))[0]["total"]

    def reserve(self, model, amount, budget):
        day = datetime.now().date().isoformat()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            total = connection.execute(
                "SELECT COALESCE(SUM(amount),0) FROM usage WHERE day=?", (day,)).fetchone()[0]
            if total + amount > budget + 1e-9:
                raise ValueError("今天的费用估算已达到预算，请调整预算或明天再试。")
            return connection.execute("INSERT INTO usage(day, model, amount, status) VALUES (?, ?, ?, 'reserved')",
                                      (day, model, amount)).lastrowid

    def complete_usage(self, usage_id, amount, status, input_tokens=0, output_tokens=0):
        self.execute("UPDATE usage SET amount=?, status=?, input_tokens=?, output_tokens=? WHERE id=?",
                     (amount, status, input_tokens, output_tokens, usage_id))

    def cached(self, fingerprint):
        rows = self.rows("SELECT body FROM ai_cache WHERE fingerprint=?", (fingerprint,))
        return rows[0]["body"] if rows else None

    def cache(self, fingerprint, body):
        self.execute("INSERT OR REPLACE INTO ai_cache VALUES (?, ?)", (fingerprint, body))

    def backup(self, destination: Path):
        with self.connect() as source:
            target = sqlite3.connect(destination)
            try:
                source.backup(target)
            finally:
                target.close()
