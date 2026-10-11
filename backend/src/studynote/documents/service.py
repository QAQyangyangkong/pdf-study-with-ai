"""Managed imports and page-preserving PDF chapter extraction."""
import hashlib
import shutil
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pymupdf

from ..storage.paths import managed_path

MAX_FILE_SIZE = 500 * 1024 * 1024
MAX_PAGE_STREAM = 20 * 1024 * 1024

# The sidecar reserves stdout for JSONL. MuPDF diagnostics may include local paths.
pymupdf.TOOLS.mupdf_display_errors(False)
pymupdf.TOOLS.mupdf_display_warnings(False)


def read_pdf(path):
    document = None
    try:
        if not 0 < Path(path).stat().st_size <= MAX_FILE_SIZE:
            raise ValueError("文件不存在、为空或超过 500 MB。")
        document = pymupdf.open(path, filetype="pdf")
        if not document.is_pdf:
            raise ValueError("PDF 无法解析，请检查文件是否完整。")
        if document.needs_pass and not document.authenticate(""):
            raise ValueError("PDF 已加密，请先使用有权限的工具解除密码。")
        if not document.page_count:
            raise ValueError("PDF 没有可读取的页面。")
        return document  # Callers must use a with block to release the file handle.
    except ValueError:
        if document is not None:
            document.close()
        raise
    except Exception as error:
        if document is not None:
            document.close()
        # A failed MuPDF constructor can retain its native file stream in traceback
        # locals on Windows. Release that chain before cleaning the managed snapshot.
        while error is not None:
            previous = error.__cause__ or error.__context__
            error.__traceback__ = error.__cause__ = error.__context__ = None
            error = previous
        raise ValueError("PDF 无法解析，请检查文件是否完整。") from None


def page_text(page):
    # Check decoded page / form streams before invoking the text interpreter.
    total = 0
    streams = set(page.get_contents()) | {item[0] for item in page.get_xobjects()}
    for xref in streams:
        total += len(page.parent.xref_stream(xref) or b"")
        if total > MAX_PAGE_STREAM:
            raise ValueError("单页内容过大，请先压缩 PDF 或选择其他页面。")
    return page.get_text("text", flags=pymupdf.TEXTFLAGS_TEXT & ~pymupdf.TEXT_PRESERVE_IMAGES) or ""


def extract_pdf(reader, start, end):
    validate_range(start, end, reader.page_count)
    parts = []
    for number in range(start, end + 1):
        text = page_text(reader.load_page(number - 1)).strip()
        parts.append(f"[PDF 第 {number} 页]\n{text}")
    return "\n\n".join(parts)


def validate_range(start, end, total):
    if type(start) is not int or type(end) is not int or not 1 <= start <= end <= total:
        raise ValueError(f"页码必须满足 1 ≤ 起始页 ≤ 结束页 ≤ {total}，使用 PDF 实际页码。")


def has_text(text):
    # Page markers alone do not count as extracted content.
    return any(line.strip() for line in text.splitlines() if not line.startswith("[PDF 第 "))


def read_docx(path):
    try:
        with zipfile.ZipFile(path) as archive:
            item = archive.getinfo("word/document.xml")
            if item.file_size > 20 * 1024 * 1024:
                raise ValueError("Word 正文过大，请拆成较小的试卷。")
            root = ElementTree.fromstring(archive.read(item))
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        return "\n".join(
            "".join(t.text or "" for t in p.findall(".//w:t", ns))
            for p in root.findall(".//w:p", ns))
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError) as error:
        raise ValueError("Word 文件无法解析，请使用 .docx 格式。") from error


class DocumentService:
    def __init__(self, database, data_dir):
        self.db = database
        self.data_dir = Path(data_dir)
        for folder in ("documents", "chapters"):
            (self.data_dir / folder).mkdir(parents=True, exist_ok=True)

    def import_file(self, source, kind="textbook", course="", year=""):
        source = Path(source)
        if kind not in {"textbook", "exam"}:
            raise ValueError("请选择教材或试卷。")
        allowed = {".pdf"} if kind == "textbook" else {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"}
        suffix = source.suffix.lower()
        if suffix not in allowed:
            raise ValueError("教材支持 PDF；试卷支持 PDF、DOCX、TXT、PNG 和 JPG。旧版 DOC 请先转换。")
        if not source.is_file() or not 0 < source.stat().st_size <= MAX_FILE_SIZE:
            raise ValueError("文件不存在、为空或超过 500 MB。")
        # Snapshot first, then hash and validate the managed copy.
        temporary = self.data_dir / "documents" / f"{uuid.uuid4().hex}.tmp"
        try:
            shutil.copyfile(source, temporary)
            with temporary.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            existing = self.db.rows(
                "SELECT id FROM documents WHERE digest=? AND kind=? AND course=? AND year=?",
                (digest, kind, course.strip(), year.strip()))
            if existing:
                return existing[0]["id"]
            pages = 0
            if suffix == ".pdf":
                with read_pdf(temporary) as pdf:
                    pages = pdf.page_count
            status = "待按页提取" if suffix == ".pdf" else "可提取文字"
            if suffix in {".png", ".jpg", ".jpeg"}:
                status = "需要 OCR"
            elif suffix == ".docx":
                read_docx(temporary)
            elif suffix == ".txt":
                temporary.read_text(encoding="utf-8-sig")
            relative = Path("documents") / f"{digest}{suffix}"
            destination = self.data_dir / relative
            if not destination.exists():
                temporary.replace(destination)
            return self.db.execute(
                "INSERT INTO documents(title,kind,course,year,digest,path,pages,status) VALUES(?,?,?,?,?,?,?,?)",
                (source.stem, kind, course.strip(), year.strip(), digest, relative.as_posix(), pages, status))
        finally:
            temporary.unlink(missing_ok=True)

    def bookmark_ranges(self, document_id):
        document = self.db.get("documents", document_id)
        starts = {}
        with read_pdf(managed_path(self.data_dir, document["path"])) as pdf:
            for level, title, number in pdf.get_toc():
                # TOC targets use one-based physical pages, regardless of page labels.
                if level == 1 and 1 <= number <= pdf.page_count:
                    starts.setdefault(number, str(title))
        if not starts:
            return []
        starts.setdefault(1, "前置内容")
        ordered = sorted(starts)
        return [(starts[start], start, ordered[i + 1] - 1 if i + 1 < len(ordered) else document["pages"])
                for i, start in enumerate(ordered)]

    def create_chapter(self, document_id, title, start, end):
        document = self.db.get("documents", document_id)
        if not title.strip():
            raise ValueError("请填写章节名称。")
        validate_range(start, end, document["pages"])
        relative = Path("chapters") / f"{uuid.uuid4().hex}.pdf"
        destination = self.data_dir / relative
        try:
            with read_pdf(managed_path(self.data_dir, document["path"])) as pdf, pymupdf.open() as chapter:
                text = extract_pdf(pdf, start, end)
                chapter.insert_pdf(pdf, from_page=start - 1, to_page=end - 1)
                chapter.save(destination, garbage=3, deflate=True)
            return self.db.execute(
                "INSERT INTO chapters(document_id,title,start_page,end_page,text,path) VALUES(?,?,?,?,?,?)",
                (document_id, title.strip(), start, end, text, relative.as_posix()))
        except Exception:
            destination.unlink(missing_ok=True)
            raise

    def exam_text(self, document_id):
        document = self.db.get("documents", document_id)
        path = managed_path(self.data_dir, document["path"])
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            if document["pages"] > 80:
                raise ValueError("试卷超过 80 页，请先拆分成较小的 PDF。")
            with read_pdf(path) as pdf:
                text = extract_pdf(pdf, 1, document["pages"])
        elif suffix == ".docx":
            text = read_docx(path)
        elif suffix == ".txt":
            text = path.read_text(encoding="utf-8-sig")
        else:
            raise ValueError("图片试卷需要 OCR。本雏形不自动识别图片，请先导入识别后的 TXT、DOCX 或文字 PDF。")
        if not has_text(text):
            raise ValueError("没有提取到文字，可能是扫描件，需要先进行 OCR。")
        return text
