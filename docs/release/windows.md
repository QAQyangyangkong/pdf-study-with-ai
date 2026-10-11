# Windows 构建与恢复

运行 pnpm build:desktop：先检查，再 PyInstaller 打包 Python，复制为带目标三元组后缀的 Sidecar，最后构建 Tauri NSIS 当前用户安装包并验证原生启动。

输出：

- StudyNote_0.2.0_x64-setup.exe，位于项目根目录（本机为 D:\pdf分割），方便直接找到并安装。
- apps/desktop/src-tauri/target/release/studynote-desktop.exe；单独复制时同时携带同目录 studynote-backend.exe。
- apps/desktop/src-tauri/target/release/bundle/nsis/StudyNote_0.2.0_x64-setup.exe。

原生启动验证成功后，构建脚本自动把同名安装包复制到项目根目录；原构建产物保留。根目录安装包不加入 Git。

scripts/release/smoke.ps1 在隔离目录隐藏启动真正的桌面程序；只有 React 加载、Rust IPC 与打包 Python 返回 workspace 后生成报告并退出。

Python 打包后还通过生产 JSONL 执行真实 PDF 导入、单页导出、章节拆分和 FTS5 搜索，防止只验证程序入口却遗漏 PyMuPDF 动态库或 SQLite 搜索能力。

安装包未签名，不配置更新器。目标电脑需要 WebView2，安装器可联网引导安装。全新电脑首次安装/卸载、无网络安装、签名与升级尚需正式发布前验证。

备份 ZIP 包含一致 SQLite 快照、教材和章节，不含 Key。恢复时先关闭程序、另存现有数据目录，再把可信备份中的 study.sqlite3、documents、chapters 解压回应用数据目录，重新配置 Key。当前没有恢复向导，不在运行时覆盖数据库。
