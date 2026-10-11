from pathlib import Path
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject


def make_pdf(path: Path, texts=("Ohm law V = I R", "Circuit current", "Practice questions"), bookmarks=False):
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=300, height=400)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                 NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({
            NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 20 350 Td ({text}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    if bookmarks:
        writer.add_outline_item("Chapter One", 1)
        writer.add_outline_item("Chapter Two", 2)
    with path.open("wb") as file:
        writer.write(file)
    return path


class FakeKeys:
    def load(self):
        return "test-key-never-log"


def fake_response(body="# 学习笔记\n\n欧姆定律。", inputs=40, outputs=60):
    return {"choices": [{"message": {"content": body}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": inputs, "completion_tokens": outputs}}
