"""Exercise search as users type it and index changes as notes are edited."""
import json
from pathlib import Path
import tempfile
import unittest

from studynote.database.repositories.workspace import Database, SCHEMA_VERSION
from studynote.notes.service import restore_version
from studynote.search.service import search_notes


class FullTextSearchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.db = Database(self.root / "study.sqlite3")

    def tearDown(self):
        self.temporary.cleanup()

    def ids(self, query, topic=""):
        return {note["id"] for note in self.db.notes(query, topic)}

    def test_chinese_substrings_in_titles_and_bodies_and_short_queries(self):
        title = self.db.save_note("欧姆定律与电路", "基础概念")
        body = self.db.save_note("电学应用", "复习欧姆定律计算串联电路电压。")
        self.db.save_note("概率统计", "随机变量")
        self.assertEqual(self.ids("姆定律"), {title, body})
        self.assertEqual(self.ids("串联电路"), {body})
        self.assertEqual(self.ids("欧姆"), {title, body})
        self.assertEqual(self.ids("姆"), {title, body})
        self.assertEqual(self.ids("没有的词"), set())

    def test_english_is_case_insensitive_and_matches_mid_word(self):
        note = self.db.save_note("Kirchhoff's Circuit Laws", "CURRENT = Voltage / Resistance")
        self.assertEqual(self.ids("circuit"), {note})
        self.assertEqual(self.ids("RRENT"), {note})
        self.assertEqual(self.ids("VO"), {note})
        self.assertEqual(self.ids("voltage / resistance"), {note})

    def test_query_operators_quotes_and_sql_wildcards_are_literal(self):
        title = '公式 "I=U/R" AND 欧姆 OR 电压'
        body = "100% 与 a_b，title:电路、NEAR(x y)、x*y；'; DROP TABLE notes; --"
        literal = self.db.save_note(title, body)
        self.db.save_note("欧姆定律", "普通内容，不含运算符")
        for query in ['"I=U/R"', "AND 欧姆", "OR 电压", "100%", "a_b",
                      "title:电路", "NEAR(x y)", "x*y", "'; DROP TABLE notes; --", "%", "_"]:
            with self.subTest(query=query):
                self.assertEqual(self.ids(query), {literal})
        self.assertEqual(self.ids("欧姆 OR 不存在"), set())
        self.assertEqual(len(self.db.notes()), 2)

    def test_topic_filter_and_note_view_preserve_sources_and_tags(self):
        source = ["教材一 / PDF 第 1-2 页"]
        first = self.db.save_note("欧姆定律", "电阻电流关系", source, ["电路", "基础"])
        self.db.save_note("欧姆定律应用", "电阻计算", ["教材二"], ["电学"])
        results = search_notes(self.db, "欧姆定律", "电路")
        self.assertEqual([note["id"] for note in results], [first])
        self.assertEqual(results[0]["sources"], source)
        self.assertEqual(results[0]["tags"], ["基础", "电路"])
        self.assertEqual(self.ids("欧姆", "电路"), {first})
        self.assertEqual(self.ids("", "电学"), {2})
        self.assertEqual(self.ids("欧姆定律", "电路' OR 1=1 --"), set())

    def test_edit_and_restore_replace_index_without_losing_provenance(self):
        note = self.db.save_note("旧概念标题", "欧姆定律原文", ["原始教材"], ["电路"])
        original_version = self.db.versions(note)[0]["id"]
        self.db.save_note("新概念标题", "基尔霍夫方程", tags=["电路"], note_id=note)
        self.assertEqual(self.ids("欧姆定律"), set())
        self.assertEqual(self.ids("旧概念"), set())
        self.assertEqual(self.ids("基尔霍夫"), {note})
        restore_version(self.db, note, original_version)
        self.assertEqual(self.ids("欧姆定律"), {note})
        self.assertEqual(self.ids("旧概念"), {note})
        self.assertEqual(self.ids("基尔霍夫"), set())
        self.assertEqual(json.loads(self.db.get("notes", note)["sources"]), ["原始教材"])
        self.assertEqual(len(self.db.versions(note)), 3)
        self.db.execute("INSERT INTO notes_fts(notes_fts,rank) VALUES('integrity-check',1)")

    def test_delete_cascades_and_removes_index_then_id_reuse_is_clean(self):
        note = self.db.save_note("删除标题", "删除正文关键词", tags=["电路"])
        self.db.execute("DELETE FROM notes WHERE id=?", (note,))
        self.assertEqual(self.ids("正文关键词"), set())
        self.assertEqual(self.db.versions(note), [])
        self.assertEqual(self.db.tags(note), [])
        replacement = self.db.save_note("替代标题", "替代正文关键词")
        self.assertEqual(self.ids("删除正文"), set())
        self.assertEqual(self.ids("替代正文"), {replacement})
        self.db.execute("INSERT INTO notes_fts(notes_fts,rank) VALUES('integrity-check',1)")

    def test_failed_save_rolls_back_index_content_and_versions_together(self):
        note = self.db.save_note("原始标题", "原始正文概念", tags=["电路"])
        self.db.execute("""CREATE TRIGGER reject_topics BEFORE INSERT ON note_topics BEGIN
          SELECT RAISE(ABORT,'test rejection');
        END""")
        with self.assertRaisesRegex(Exception, "test rejection"):
            self.db.save_note("未提交标题", "未提交正文概念", tags=["拒绝"], note_id=note)
        self.assertEqual(self.ids("原始正文"), {note})
        self.assertEqual(self.ids("未提交正文"), set())
        self.assertEqual(self.db.tags(note), ["电路"])
        self.assertEqual(len(self.db.versions(note)), 1)

    def test_backup_and_reopen_preserve_search_index(self):
        note = self.db.save_note("电路知识", "复习基尔霍夫定律", tags=["电学"])
        restored_path = self.root / "restored.sqlite3"
        self.db.backup(restored_path)
        restored = Database(restored_path)
        self.assertEqual([item["id"] for item in restored.notes("基尔霍夫", "电学")], [note])
        self.assertEqual(restored.rows("PRAGMA user_version")[0]["user_version"], SCHEMA_VERSION)
        self.assertFalse((self.root / "backups").exists())

    def test_three_character_search_uses_full_text_virtual_index(self):
        self.db.save_note("搜索索引", "实际正文文本")
        plan = self.db.rows(
            "EXPLAIN QUERY PLAN SELECT rowid FROM notes_fts WHERE notes_fts MATCH ?", ('"正文文本"',))
        self.assertTrue(any("VIRTUAL TABLE INDEX" in item["detail"] and "M" in item["detail"]
                            for item in plan), plan)


if __name__ == "__main__":
    unittest.main()
