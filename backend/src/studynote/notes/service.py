import json


def note_view(database, note):
    return {**note, "sources": json.loads(note["sources"]), "tags": database.tags(note["id"])}


def restore_version(database, note_id, version_id):
    versions = database.rows("SELECT * FROM note_versions WHERE id=? AND note_id=?", (version_id, note_id))
    if not versions:
        raise ValueError("笔记版本不存在。")
    version = versions[0]
    return database.save_note(version["title"], version["body"], tags=database.tags(note_id), note_id=note_id)
