from pathlib import Path
import pymupdf


def make_pdf(path: Path, texts=("Ohm law V = I R", "Circuit current", "Practice questions"), bookmarks=False):
    with pymupdf.open() as document:
        for text in texts:
            page = document.new_page(width=300, height=400)
            page.insert_text((20, 50), text, fontsize=12)
        if bookmarks:
            document.set_toc([[1, "Chapter One", 2], [1, "Chapter Two", 3]])
        document.save(path)
    return path


class FakeKeys:
    def load(self):
        return "test-key-never-log"


def fake_response(body="# 学习笔记\n\n欧姆定律。", inputs=40, outputs=60):
    return {"choices": [{"message": {"content": body}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": inputs, "completion_tokens": outputs}}
