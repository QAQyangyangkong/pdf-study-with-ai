import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from studynote.database.repositories.workspace import Database, SCHEMA, SCHEMA_VERSION
from studynote.database.migrations.v2 import SQL as V2_SQL
from studynote.core.config import default_data_dir


class LegacyMigrationTests(unittest.TestCase):
    def test_v1_notes_are_preserved_backed_up_and_versioned(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'study.sqlite3'
            with closing(sqlite3.connect(path)) as connection:
                connection.executescript(SCHEMA)
                connection.execute("INSERT INTO notes(id,title,body,sources,kind,updated_at) VALUES(7,'旧笔记','欧姆定律原文','[\"旧教材\"]','note','2026-10-10')")
                connection.commit()
            database=Database(path)
            self.assertEqual(database.get('notes',7)['body'],'欧姆定律原文')
            self.assertEqual(len(database.versions(7)),1)
            self.assertEqual([note['id'] for note in database.notes('欧姆定律')],[7])
            self.assertEqual(database.rows('PRAGMA user_version')[0]['user_version'],SCHEMA_VERSION)
            backup=next((path.parent/'backups').glob('schema-v1-*.sqlite3'))
            with closing(sqlite3.connect(backup)) as connection:
                self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0],1)
                self.assertEqual(connection.execute('SELECT body FROM notes WHERE id=7').fetchone()[0],'欧姆定律原文')
                self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name='notes_fts'").fetchone())
            database.save_note('新标题','新理解',note_id=7)
            self.assertEqual(len(database.versions(7)),2)
            Database(path)
            self.assertEqual(len(list((path.parent/'backups').glob('*.sqlite3'))),1)

    def test_v2_data_versions_settings_and_usage_are_preserved_and_backed_up(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'study.sqlite3'
            with closing(sqlite3.connect(path)) as connection:
                connection.executescript(SCHEMA)
                connection.execute("INSERT INTO notes VALUES(9,'电路复习','基尔霍夫方程','[\"教材 A\"]','note','2026-10-10')")
                connection.execute("INSERT INTO topics VALUES(4,'电路')")
                connection.execute("INSERT INTO note_topics VALUES(9,4)")
                connection.execute("INSERT INTO settings VALUES('daily_budget','2.5')")
                connection.execute("INSERT INTO usage VALUES(3,'2026-10-11','deepseek-chat',0.7,'completed',100,200)")
                connection.commit()
                connection.executescript(V2_SQL)
            database=Database(path)
            self.assertEqual([note['id'] for note in database.notes('基尔霍夫','电路')],[9])
            self.assertEqual(database.get('notes',9)['sources'],'["教材 A"]')
            self.assertEqual(database.setting('daily_budget'),2.5)
            self.assertAlmostEqual(database.spent('2026-10-11'),0.7)
            self.assertEqual(database.versions(9)[0]['body'],'基尔霍夫方程')
            backups=list((path.parent/'backups').glob('schema-v2-*.sqlite3'))
            self.assertEqual(len(backups),1)
            with closing(sqlite3.connect(backups[0])) as backup:
                self.assertEqual(backup.execute('PRAGMA user_version').fetchone()[0],2)
                self.assertIsNone(backup.execute("SELECT name FROM sqlite_master WHERE name='notes_fts'").fetchone())
                self.assertEqual(backup.execute('SELECT note_id FROM note_versions').fetchone()[0],9)
            database.execute("INSERT INTO notes_fts(notes_fts,rank) VALUES('integrity-check',1)")
            Database(path)
            self.assertEqual(len(list((path.parent/'backups').glob('*.sqlite3'))),1)

    def test_migration_failure_rolls_back_entire_v1_upgrade(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'study.sqlite3'
            with closing(sqlite3.connect(path)) as connection:
                connection.executescript(SCHEMA)
                connection.execute("INSERT INTO notes VALUES(1,'旧笔记','保留原文','[]','note','2026-10-10')")
                connection.commit()
            with patch('studynote.database.migrations.v3.apply',side_effect=RuntimeError('index failed')):
                with self.assertRaisesRegex(RuntimeError,'index failed'):
                    Database(path)
            with closing(sqlite3.connect(path)) as connection:
                self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0],1)
                self.assertEqual(connection.execute('SELECT body FROM notes WHERE id=1').fetchone()[0],'保留原文')
                self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name='note_versions'").fetchone())
            self.assertEqual(len(list((path.parent/'backups').glob('schema-v1-*.sqlite3'))),1)
            self.assertEqual([note['id'] for note in Database(path).notes('保留原文')],[1])

    def test_existing_study_desk_directory_is_reused(self):
        with tempfile.TemporaryDirectory() as temporary:
            previous=Path(temporary)/'StudyDesk'
            previous.mkdir()
            (previous/'study.sqlite3').touch()
            with patch.dict('os.environ',{'LOCALAPPDATA':temporary}):
                self.assertEqual(default_data_dir(),previous)
