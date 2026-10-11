# 验证记录

架构迁移保留原有文档、预算、来源与导出测试，增加 IPC、旧库迁移、React 和完整端到端覆盖。

- Python 业务 / IPC / 开发桥接授权：39 项。
- 旧数据库迁移与目录兼容：2 项。
- React / 共享协议：8 项。
- Playwright：PDF → 分章 → 缓存生成 → 编辑 → 主题 → Obsidian 导出，检查 PDF canvas 和页面运行错误。
- TypeScript 类型、生产前端构建、Python 编译。
- PyInstaller 打包与隔离启动；Tauri 原生 WebView → Rust → Python 启动验证。

人工生成两页 PDF 用作夹具，测试隔离目录，不调用付费 API。Tabbit 检查实际首页和阅读布局。真实模型质量、账户计费、首次安装/卸载、签名和更新不属于本次验证范围。
