"""Portable Markdown notes and topic indexes with stable Obsidian links."""
import json
import re
from datetime import datetime
from pathlib import Path


def safe_name(value):
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f#\[\]]', "_", value).strip(" .")
    return (cleaned or "未命名")[:80]


def export_vault(database, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    # Each export is a new folder; never replace existing user notes.
    root = destination / ("StudyDesk-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    root.mkdir()
    notes_dir, topics_dir = root / "笔记", root / "知识主题"
    notes_dir.mkdir()
    topics_dir.mkdir()
    notes = database.notes()
    filenames = {note["id"]: f"{note['id']}-{safe_name(note['title'])}" for note in notes}
    for note in notes:
        tags = database.tags(note["id"])
        sources = json.loads(note["sources"])
        # JSON quoted strings are also valid YAML strings.
        header = "---\n" + f"title: {json.dumps(note['title'], ensure_ascii=False)}\n"
        header += f"study_desk_id: {note['id']}\nupdated: {note['updated_at']}\n"
        header += f"topics: {json.dumps(tags, ensure_ascii=False)}\n---\n\n"
        body = header + note["body"] + "\n\n## 材料来源\n\n"
        body += "\n".join(f"- {source}" for source in sources) if sources else "手动创建的笔记。"
        (notes_dir / (filenames[note["id"]] + ".md")).write_text(body + "\n", encoding="utf-8")
    topics = database.rows("SELECT t.id,t.name FROM topics t WHERE EXISTS "
                           "(SELECT 1 FROM note_topics nt WHERE nt.topic_id=t.id) ORDER BY t.name")
    for topic in topics:
        related = database.notes(topic=topic["name"])
        body = f"# {topic['name']}\n\n" + "\n".join(
            f"- [[笔记/{filenames[note['id']]}]]" for note in related)
        (topics_dir / f"{topic['id']}-{safe_name(topic['name'])}.md").write_text(body + "\n", encoding="utf-8")
    (root / "开始阅读.md").write_text(
        "# Study Desk 导出\n\n将此文件夹作为 Obsidian 仓库打开，或复制到已有仓库。\n\n"
        "## 笔记\n\n" + "\n".join(f"- [[笔记/{name}]]" for name in filenames.values()), encoding="utf-8")
    return root
