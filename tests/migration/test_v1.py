import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from studynote.database.repositories.workspace import Database, SCHEMA
from studynote.core.config import default_data_dir


class LegacyMigrationTests(unittest.TestCase):
    def test_v1_notes_are_preserved_backed_up_and_versioned(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'study.sqlite3'
            with closing(sqlite3.connect(path)) as connection:
                connection.executescript(SCHEMA)
                connection.execute("INSERT INTO notes(id,title,body,sources,kind,updated_at) VALUES(7,'旧笔记','原文','[\"旧教材\"]','note','2026-10-10')")
                connection.commit()
            database=Database(path)
            self.assertEqual(database.get('notes',7)['body'],'原文')
            self.assertEqual(len(database.versions(7)),1)
            backup=next((path.parent/'backups').glob('schema-v1-*.sqlite3'))
            with closing(sqlite3.connect(backup)) as connection:
                self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0],1)
                self.assertEqual(connection.execute('SELECT body FROM notes WHERE id=7').fetchone()[0],'原文')
            database.save_note('新标题','新理解',note_id=7)
            self.assertEqual(len(database.versions(7)),2)
            Database(path)
            self.assertEqual(len(list((path.parent/'backups').glob('*.sqlite3'))),1)

    def test_existing_study_desk_directory_is_reused(self):
        with tempfile.TemporaryDirectory() as temporary:
            previous=Path(temporary)/'StudyDesk'
            previous.mkdir()
            (previous/'study.sqlite3').touch()
            with patch.dict('os.environ',{'LOCALAPPDATA':temporary}):
                self.assertEqual(default_data_dir(),previous)
