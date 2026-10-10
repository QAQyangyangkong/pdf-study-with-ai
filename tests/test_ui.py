import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest.mock import patch

from study_desk.ai import AIService
from study_desk.app import StudyApp
from study_desk.workspace import Workspace
from tests.helpers import FakeKeys, fake_response, make_pdf


class UITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.workspace = Workspace(self.directory / "data")
        self.workspace.ai = AIService(self.workspace.db, FakeKeys(), lambda *args: fake_response())
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = StudyApp(self.root, self.workspace)

    def tearDown(self):
        self.app.executor.shutdown(wait=True)
        if not self.app.closed:
            self.root.after_cancel(self.app.poll_id)
            self.root.destroy()
        self.temp.cleanup()

    def pump(self):
        deadline = time.monotonic() + 10
        while self.app.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(.02)
        self.root.update()
        self.assertFalse(self.app.busy, "Background task did not complete")

    def find_send(self, parent):
        for child in parent.winfo_children():
            if isinstance(child, ttk.Button) and child.cget("text") in ("确认生成", "使用缓存"):
                return child
            found = self.find_send(child)
            if found:
                return found
        return None

    def send_preview(self):
        dialog = next(child for child in self.root.winfo_children() if isinstance(child, tk.Toplevel))
        send = self.find_send(dialog)
        self.assertIsNotNone(send)
        send.invoke()
        self.pump()

    def test_textbook_to_notes_topics_exams_and_export(self):
        book = self.workspace.documents.import_file(make_pdf(self.directory / "textbook.pdf"), course="电路")
        self.app.refresh()
        self.app.books.selection_set(str(book))
        self.root.update()
        self.app.chapter_title.set("欧姆定律")
        self.app.start_page.set("1")
        self.app.end_page.set("2")
        self.app.split_chapter()
        self.pump()
        self.assertIn("Ohm law", self.app.chapter_preview.get("1.0", "end"))
        self.app.generate_chapter()
        self.send_preview()
        self.assertEqual(self.app.note_title.get(), "欧姆定律")
        self.app.note_tags.set("电路，基础")
        self.app.note_body.insert("end", "\n手动补充的复习提示")
        self.app.save_note()
        note = self.workspace.db.get("notes", self.app.note_id)
        self.assertIn("手动补充", note["body"])
        self.assertIn("PDF 第 1-2 页", note["sources"])
        self.assertEqual(self.workspace.db.tags(note["id"]), ["基础", "电路"])
        exam = self.directory / "exam.txt"
        exam.write_text("1. Calculate current with V=12 and R=4.", encoding="utf-8")
        exam_id = self.workspace.documents.import_file(exam, "exam", "电路", "2024")
        self.app.refresh()
        self.app.exams.selection_set(str(exam_id))
        self.app.analyze_exams()
        self.pump()
        self.send_preview()
        self.assertEqual(len(self.workspace.db.notes()), 2)
        self.assertEqual(self.workspace.db.get("notes", self.app.note_id)["kind"], "exam-report")
        self.assertEqual(self.app.note_list.item(str(self.app.note_id), "values")[1], "考点报告")
        destination = self.directory / "export"
        with patch("study_desk.app.filedialog.askdirectory", return_value=str(destination)), \
             patch("study_desk.app.messagebox.showinfo"):
            self.app.export()
            self.pump()
        self.assertEqual(len(list(destination.rglob("笔记/*.md"))), 2)
        self.assertIn("2 篇笔记", self.app.summary.get())

    def test_unsaved_changes_can_cancel_navigation_and_close(self):
        self.app.note_title.set("未保存")
        self.app.note_body.insert("1.0", "正文")
        with patch("study_desk.app.messagebox.askyesnocancel", return_value=None):
            self.app.new_note()
            self.app.close()
        self.assertEqual(self.app.note_title.get(), "未保存")
        self.assertFalse(self.app.closed)

    def test_invalid_config_is_not_persisted(self):
        self.app.config_vars["input_price"].set("nan")
        with self.assertRaises(ValueError):
            self.app.save_config()
        self.assertIsNone(self.workspace.db.setting("ai"))
