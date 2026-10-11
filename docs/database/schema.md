# 数据模型

应用目录 study.sqlite3，PRAGMA user_version=2。连接启用外键，SQL 值参数化。

| 表 | 用途 |
| --- | --- |
| documents / chapters | 文件摘要、类型、课程、托管路径、实际页码与文字 |
| notes | Markdown、来源、类型和时间 |
| note_versions | 每次保存或恢复的标题、正文和来源快照 |
| topics / note_topics | 主题与笔记关联 |
| settings | 引导与公开配置 |
| ai_cache | 端点、模型、提示词和输出限制摘要对应结果 |
| usage | 日期、模型、预算预留、用量及计费状态 |

v1 升级前使用 SQLite backup API 写 backups/schema-v1-*.sqlite3。事务创建历史表并给旧笔记生成初始版本。较新模式拒绝降级打开。

历史包含标题、正文和来源；恢复版本沿用当前标签。查询是字面子串，未实现 FTS / 向量索引。预算通过 BEGIN IMMEDIATE 原子预留。
