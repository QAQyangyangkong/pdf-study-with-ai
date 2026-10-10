import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from pypdf import PdfReader, PdfWriter

from study_desk.documents import has_text, validate_range
from study_desk.workspace import Workspace
from tests.helpers import make_pdf


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = Workspace(self.root / "工作区")
        self.service = self.workspace.documents
        self.source = make_pdf(self.root / "电路教材.pdf", bookmarks=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_import_duplicate_managed_copy_and_metadata(self):
        original = hashlib.sha256(self.source.read_bytes()).hexdigest()
        item = self.service.import_file(self.source, course="电路")
        self.assertEqual(item, self.service.import_file(self.source, course="电路"))
        self.assertNotEqual(item, self.service.import_file(self.source, "exam", "电路", "2025"))
        document = self.workspace.db.get("documents", item)
        self.assertEqual(document["pages"], 3)
        self.assertEqual(original, hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.source.unlink()
        chapter_id = self.service.create_chapter(item, "基础", 1, 2)
        chapter = self.workspace.db.get("chapters", chapter_id)
        self.assertIn("[PDF 第 1 页]", chapter["text"])
        self.assertIn("Ohm law", chapter["text"])
        self.assertNotIn("Practice questions", chapter["text"])
        reader = PdfReader(self.workspace.directory / chapter["path"])
        self.assertEqual(len(reader.pages), 2)
        self.assertEqual(reader.pages[0].extract_text(), "Ohm law V = I R")
        self.assertEqual(float(reader.pages[0].mediabox.width), 300)

    def test_bookmarks_cover_front_matter_without_overlap(self):
        item = self.service.import_file(self.source)
        self.assertEqual(self.service.bookmark_ranges(item),
                         [("前置内容", 1, 1), ("Chapter One", 2, 2), ("Chapter Two", 3, 3)])

    def test_invalid_range_does_not_write_chapter(self):
        item = self.service.import_file(self.source)
        for start, end in ((0, 2), (2, 1), (1, 4), (True, 2), (1.0, 2)):
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                self.service.create_chapter(item, "bad", start, end)
        self.assertEqual(self.workspace.db.rows("SELECT * FROM chapters"), [])
        self.assertEqual(list((self.workspace.directory / "chapters").iterdir()), [])

    def test_scan_is_split_but_text_is_not_fabricated(self):
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=400)
        scan = self.root / "scan.pdf"
        with scan.open("wb") as file:
            writer.write(file)
        item = self.service.import_file(scan)
        chapter_id = self.service.create_chapter(item, "scan", 1, 1)
        self.assertFalse(has_text(self.workspace.db.get("chapters", chapter_id)["text"]))
        with self.assertRaisesRegex(ValueError, "OCR"):
            self.service.exam_text(item)

    def test_encrypted_and_corrupt_pdf_leave_no_records_or_temporary_files(self):
        bad = self.root / "bad.pdf"
        bad.write_bytes(b"not a PDF")
        with self.assertRaises(ValueError):
            self.service.import_file(bad)
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt("password")
        with bad.open("wb") as file:
            writer.write(file)
        with self.assertRaisesRegex(ValueError, "加密"):
            self.service.import_file(bad)
        self.assertFalse(self.workspace.db.rows("SELECT * FROM documents"))
        self.assertFalse(list((self.workspace.directory / "documents").iterdir()))

    def test_docx_preserves_paragraphs_and_table_text(self):
        docx = self.root / "exam.docx"
        xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>欧姆定律</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>计算电流</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>'
        with zipfile.ZipFile(docx, "w") as archive:
            archive.writestr("word/document.xml", xml)
        item = self.service.import_file(docx, "exam", "电路", "2024")
        self.assertEqual(self.service.exam_text(item), "欧姆定律\n计算电流")

    def test_image_import_is_explicitly_pending_ocr(self):
        image = self.root / "exam.png"
        image.write_bytes(b"image placeholder")
        item = self.service.import_file(image, "exam")
        self.assertEqual(self.workspace.db.get("documents", item)["status"], "需要 OCR")
        with self.assertRaisesRegex(ValueError, "OCR"):
            self.service.exam_text(item)

    def test_utf8_bom_and_old_word_rejection(self):
        text = self.root / "exam.txt"
        text.write_text("一、计算电流", encoding="utf-8-sig")
        item = self.service.import_file(text, "exam")
        self.assertEqual(self.service.exam_text(item), "一、计算电流")
        old = self.root / "exam.doc"
        old.write_bytes(b"old word")
        with self.assertRaisesRegex(ValueError, "DOC"):
            self.service.import_file(old, "exam")
