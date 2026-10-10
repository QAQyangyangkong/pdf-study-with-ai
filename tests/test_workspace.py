import json
import os
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path

from study_desk.db import Database
from study_desk.export import export_vault
from study_desk.security import KeyStore
from study_desk.workspace import Workspace
from tests.helpers import make_pdf


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = Workspace(self.root / "data")
        self.db = self.workspace.db

    def tearDown(self):
        self.temp.cleanup()

    def test_note_update_keeps_source_and_topics_join_across_books(self):
        first = self.db.save_note("教材一", "欧姆定律", ["书一 / PDF 第 1 页"], ["电路", " 电路 "])
        second = self.db.save_note("教材二", "应用", ["书二 / PDF 第 2 页"], ["电路"])
        self.assertEqual({n["id"] for n in self.db.notes(topic="电路")}, {first, second})
        self.db.save_note("更正标题", "新正文", tags=["电学"], note_id=first)
        self.assertEqual(json.loads(self.db.get("notes", first)["sources"]), ["书一 / PDF 第 1 页"])
        self.assertEqual(self.db.tags(first), ["电学"])
        self.assertEqual([n["id"] for n in self.db.notes(topic="电路")], [second])
        self.assertEqual(len(self.db.notes(search="新正文")), 1)
        self.assertEqual(self.db.notes(search="%"), [])

    def test_invalid_notes_do_not_create_or_update(self):
        with self.assertRaises(ValueError):
            self.db.save_note("", "body")
        with self.assertRaises(ValueError):
            self.db.save_note("title", "body", note_id=999)
        self.assertEqual(self.db.notes(), [])

    def test_export_safe_filenames_collision_free_links_and_provenance(self):
        first = self.db.save_note("same/[title]", "# 概念\n内容", ["PDF 第 2 页"], ["电路/基础"])
        second = self.db.save_note("same/[title]", "# 应用\n内容", ["另一教材"], ["电路/基础"])
        vault = export_vault(self.db, self.root / "vault")
        files = sorted((vault / "笔记").glob("*.md"))
        self.assertEqual(len(files), 2)
        self.assertTrue(files[0].name.startswith(str(first)))
        self.assertTrue(files[1].name.startswith(str(second)))
        self.assertIn("PDF 第 2 页", files[0].read_text(encoding="utf-8"))
        topic = next((vault / "知识主题").glob("*.md")).read_text(encoding="utf-8")
        for file in files:
            self.assertIn(f"[[笔记/{file.stem}]]", topic)
        other = export_vault(self.db, self.root / "vault")
        self.assertNotEqual(vault, other)
        self.assertTrue(files[0].exists())

    def test_backup_is_restorable_and_excludes_key(self):
        book = self.workspace.documents.import_file(make_pdf(self.root / "book.pdf"))
        chapter = self.workspace.documents.create_chapter(book, "chapter", 1, 2)
        self.db.save_note("note", "body", ["book / 1-2"])
        self.workspace.keys.path.write_bytes(b"encrypted-key-placeholder")
        archive_path = self.workspace.backup(self.root / "backup.zip")
        with zipfile.ZipFile(archive_path) as archive:
            self.assertNotIn("api-key.dpapi", archive.namelist())
            self.assertIn("study.sqlite3", archive.namelist())
            restored = self.root / "restored"
            archive.extractall(restored)
        workspace = Workspace(restored)
        self.assertEqual(workspace.db.notes()[0]["body"], "body")
        self.assertTrue((restored / workspace.db.get("chapters", chapter)["path"]).exists())
        self.assertEqual(workspace.documents.exam_text(book).count("[PDF 第 "), 3)

    def test_backup_inside_data_directory_is_rejected(self):
        with self.assertRaises(ValueError):
            self.workspace.backup(self.workspace.directory / "backup.zip")

    def test_reopen_is_idempotent_and_future_schema_is_not_modified(self):
        self.db.save_note("note", "body")
        self.assertEqual(len(Database(self.db.path).notes()), 1)
        with closing(sqlite3.connect(self.db.path)) as connection:
            connection.execute("PRAGMA user_version=999")
        with self.assertRaisesRegex(ValueError, "较新版本"):
            Database(self.db.path)
        with closing(sqlite3.connect(self.db.path)) as connection:
            self.assertEqual(connection.execute("PRAGMA user_version").fetchone()[0], 999)

    @unittest.skipUnless(os.name == "nt", "Windows DPAPI")
    def test_dpapi_round_trip_is_ciphertext_and_can_be_deleted(self):
        keys = KeyStore(self.workspace.directory)
        key = "local-test-secret-123"
        keys.save(key)
        self.assertNotIn(key.encode(), keys.path.read_bytes())
        self.assertEqual(keys.load(), key)
        keys.save("replacement-test-secret")
        self.assertEqual(keys.load(), "replacement-test-secret")
        keys.delete()
        with self.assertRaises(ValueError):
            keys.load()
