# Windows 构建与恢复

先生成直接启动版，再封装安装包。发布目录必须位于源码目录之外，本机使用 D:\StudyNote；可通过 STUDYNOTE_RELEASE_DIR 或 scripts/build/desktop.ps1 的 OutputDirectory 参数指定其他外部位置。

- pnpm build:portable：执行检查、打包 Python、用 Tauri --no-bundle 编译桌面程序，整理直接启动文件并验证。
- pnpm build:installer：验证已有的直接启动程序，再用 Tauri bundle --bundles nsis 封装安装包。修改代码后须先重新执行 build:portable。
- pnpm build:desktop：顺序完成上述两步。CI 使用 RUNNER_TEMP 下的独立发布目录。

输出：

- D:\StudyNote\StudyNote.exe：双击直接启动，无需先安装。
- D:\StudyNote\studynote-backend.exe：同目录的后台文件，名称须保留。
- D:\StudyNote\使用说明.txt：普通用户教程。
- D:\StudyNote\installers\StudyNote_0.2.0_x64-setup.exe：验证直接启动版后生成的当前用户安装包。

前端资源嵌入主程序，Python 和 PyMuPDF 已打包；使用者无需 Node.js、Python 或项目源码。发送直接启动版时须保留整个软件文件夹。原生编译缓存仍在 target 中，安装包完成字节校验后移到外部发布目录，不留在源码目录；之前复制到项目根目录的同名安装包会清理。程序和安装包都使用原有本地数据目录。

scripts/release/smoke.ps1 从发布文件夹隐藏启动真正的桌面程序，清除项目 PYTHONPATH，以绝对路径写报告；只有 React 加载、Rust IPC 与同目录打包 Python 返回 workspace 后生成报告并退出。

Python 打包后还通过生产 JSONL 执行真实 PDF 导入、单页导出、章节拆分和 FTS5 搜索，防止只验证程序入口却遗漏 PyMuPDF 动态库或 SQLite 搜索能力。

封装前用 SHA256 比较 NSIS 实际读取的 target/release 主程序、externalBin 后台文件与已验证的外部直接启动版；不一致时停止封装。Tauri bundle 使用 --no-binary-patching，保留已验证程序字节；当前未配置更新器。

安装包未签名，不配置更新器。目标电脑需要 WebView2，安装器可联网引导安装。全新电脑首次安装/卸载、无网络安装、签名与升级尚需正式发布前验证。

备份 ZIP 包含一致 SQLite 快照、教材和章节，不含 Key。恢复时先关闭程序、另存现有数据目录，再把可信备份中的 study.sqlite3、documents、chapters 解压回应用数据目录，重新配置 Key。当前没有恢复向导，不在运行时覆盖数据库。
