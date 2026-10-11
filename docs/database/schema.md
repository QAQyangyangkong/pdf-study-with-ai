# 数据模型

应用目录 study.sqlite3，PRAGMA user_version=3。连接启用外键，SQL 值参数化。

| 表 | 用途 |
| --- | --- |
| documents / chapters | 文件摘要、类型、课程、托管路径、实际页码与文字 |
| notes | Markdown、来源、类型和时间 |
| note_versions | 每次保存或恢复的标题、正文和来源快照 |
| notes_fts | FTS5 trigram 标题与 Markdown 正文索引 |
| topics / note_topics | 主题与笔记关联 |
| settings | 引导与公开配置 |
| ai_cache | 端点、模型、提示词和输出限制摘要对应结果 |
| usage | 日期、模型、预算预留、用量及计费状态 |

升级前使用 SQLite backup API 保存原模式数据库。v1 → v2 创建笔记历史；v2 → v3 创建 FTS5 索引和同步触发器，重建已有笔记索引。较新模式拒绝降级打开。

历史包含标题、正文和来源；恢复版本沿用当前标签。笔记 INSERT / UPDATE / DELETE 触发器自动同步索引，包括版本恢复。预算通过 BEGIN IMMEDIATE 原子预留。

搜索将用户输入作为字面短语转义后参数化 MATCH，支持中文连续字符串及英文、符号，不执行用户提供的 FTS 运算符。根据 [FTS5 trigram 限制](https://www.sqlite.org/fts5.html#the_trigram_tokenizer)，少于三个字符的搜索回退到参数化子串查询；三字符及以上使用索引，主题过滤保留精确匹配。长查询按 FTS5 BM25 排序，未实现向量检索。
