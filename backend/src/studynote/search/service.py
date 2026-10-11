from ..notes.service import note_view


def search_notes(database, query="", topic=""):
    return [note_view(database, note) for note in database.notes(query, topic)]
