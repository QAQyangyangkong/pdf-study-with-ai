"""Managed imports and page-preserving PDF chapter extraction."""
import hashlib
import shutil
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader, PdfWriter

MAX_FILE_SIZE = 500 * 1024 * 1024
MAX_PAGE_STREAM = 20 * 1024 * 1024


def read_pdf(path):
    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ValueError("PDF 已加密，请先使用有权限的工具解除密码。")
        if not reader.pages:
            raise ValueError("PDF 没有可读取的页面。")
        return reader
    except ValueError:
        raise
    except Exception as error:
        raise ValueError("PDF 无法解析，请检查文件是否完整。") from error


def page_text(page):
    contents = page.get_contents()
    if contents and len(contents.get_data()) > MAX_PAGE_STREAM:
        raise ValueError("单页内容过大，请先压缩 PDF 或选择其他页面。")
    return page.extract_text() or ""


def extract_pdf(reader, start, end):
    validate_range(start, end, len(reader.pages))
    parts = []
    for number in range(start, end + 1):
        text = page_text(reader.pages[number - 1]).strip()
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
            pages = len(read_pdf(temporary).pages) if suffix == ".pdf" else 0
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
        reader = read_pdf(self.data_dir / document["path"])
        starts = {}
        for item in reader.outline:
            if isinstance(item, list):
                continue  # Prefer top-level chapter boundaries.
            number = reader.get_destination_page_number(item)
            if number is not None and 0 <= number < len(reader.pages):
                starts.setdefault(number + 1, str(item.title))
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
        reader = read_pdf(self.data_dir / document["path"])
        text = extract_pdf(reader, start, end)
        relative = Path("chapters") / f"{uuid.uuid4().hex}.pdf"
        destination = self.data_dir / relative
        writer = PdfWriter()
        for index in range(start - 1, end):
            writer.add_page(reader.pages[index])
        try:
            with destination.open("wb") as stream:
                writer.write(stream)
            return self.db.execute(
                "INSERT INTO chapters(document_id,title,start_page,end_page,text,path) VALUES(?,?,?,?,?,?)",
                (document_id, title.strip(), start, end, text, relative.as_posix()))
        except Exception:
            destination.unlink(missing_ok=True)
            raise

    def exam_text(self, document_id):
        document = self.db.get("documents", document_id)
        path = self.data_dir / document["path"]
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            if document["pages"] > 80:
                raise ValueError("试卷超过 80 页，请先拆分成较小的 PDF。")
            text = extract_pdf(read_pdf(path), 1, document["pages"])
        elif suffix == ".docx":
            text = read_docx(path)
        elif suffix == ".txt":
            text = path.read_text(encoding="utf-8-sig")
        else:
            raise ValueError("图片试卷需要 OCR。本雏形不自动识别图片，请先导入识别后的 TXT、DOCX 或文字 PDF。")
        if not has_text(text):
            raise ValueError("没有提取到文字，可能是扫描件，需要先进行 OCR。")
        return text
