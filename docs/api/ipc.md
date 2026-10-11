# IPC v1

每行一个 UTF-8 JSON，标准输出只承载协议。权威方法枚举：packages/contracts/protocol.schema.json。

```json
{"protocol_version":1,"id":"request-1","method":"workspace.get","params":{}}
```

成功响应包含同一 id、ok:true、result；失败为 ok:false、error.code、error.message。请求上限 512 KiB，ID 1–80 字符，拒绝未定义字段。

| 方法 | 用途 |
| --- | --- |
| workspace.get / onboarding.complete | 快照与首次引导 |
| documents.import / documents.bookmarks | 导入与书签 |
| reader.page / chapters.create | 单页 PDF base64（最大 8 MiB）与分章 |
| notes.save / notes.search | 保存与查询 |
| notes.versions / notes.restore | 历史与恢复 |
| settings.save / settings.delete_key | 配置、保存或清除凭据 |
| generation.prepare / generation.start | 冻结预览与单次 token 执行 |
| tasks.get | queued / running / completed / failed |
| export.obsidian / backup.create | 本地导出和备份 |

参数白名单见 backend/src/studynote/ipc/router.py。prepare 只保留最新预览，token 仅使用一次。修改材料或配置后重新准备。Key 不回传；空 Key 保留现有凭据，删除用单独方法。
