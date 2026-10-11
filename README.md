# StudyNote

本地优先的 AI 学习笔记桌面应用雏形，采用 **React + TypeScript + shadcn/ui + Tailwind CSS + Tiptap + Tauri 2 + Python Sidecar + PyMuPDF + SQLite FTS5**。当前仓库即 StudyNote 项目根目录。

## 已实现

- 首次引导、学习首页、教材导入、PDF 页面阅读、书签提示和按页分章。
- 主模型与可选第二模型、Windows 系统凭据管理器保存 Key、发送前预览、预算、缓存与后台生成。
- Tiptap 富文本和 Markdown 原文编辑、历史版本恢复、跨教材主题聚合与 SQLite FTS5 搜索。
- Obsidian 导出、ZIP 备份、旧版数据库自动备份和升级。

试卷分析页面按规划保留为后续入口。OCR、语义检索、知识图谱、备份恢复向导、自动更新和发布签名尚未实现。

## 环境与启动

Windows 10/11 x64，Node.js 24、pnpm 11.25、Python 3.14、Rust stable、Visual Studio C++ Build Tools、WebView2。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-build.txt
pnpm install --frozen-lockfile
pnpm dev
```

浏览器开发界面：http://127.0.0.1:1420 。开发模式使用路径输入框替代原生文件对话框。先执行 `pnpm build:sidecar`，再用 `pnpm dev:desktop` 启动真正的桌面窗口。双击 run.bat 启动浏览器开发模式。

```powershell
pnpm check          # 后端、迁移、前端单测、类型和生产构建
pnpm test:e2e       # Edge 中的完整离线业务流程
pnpm build:desktop  # 检查、Python 打包、Tauri 安装包和原生启动验证
```

目标电脑无需安装 Python，需要 WebView2；首次安装可能联网获取运行时。安装包位置见 [Windows 构建](docs/release/windows.md)。

## 数据与隐私

新安装使用 `%LOCALAPPDATA%\StudyNote`；检测到旧版 `%LOCALAPPDATA%\StudyDesk\study.sqlite3` 时沿用旧目录。可用 STUDYNOTE_DATA_DIR 指定隔离目录。导入复制原文件，不改写教材。仅在确认 AI 请求后发送预览文本。Key 不进入前端响应、日志或 ZIP 备份。

API Key 保存在当前 Windows 用户的系统凭据管理器，每个工作区使用独立凭据。旧版 DPAPI 文件首次读取时自动迁移，系统保存成功后删除旧文件。数据库 v1/v2 自动备份并升级至 v3，重建已有笔记的 FTS5 索引。

费用使用可编辑的美元单价与保守 UTF-8 估算，不能替代服务商账单；请按实际账户更新配置。超时或未知计费保留预估费用，避免无限重试。

## 结构与文档

apps/desktop：React 与 Rust；backend：Python 业务；packages/contracts：共享协议；scripts：开发、构建与验证；tests：端到端、夹具和迁移。

- [产品范围](docs/product/mvp.md)
- [架构](docs/architecture/overview.md)
- [IPC](docs/api/ipc.md)
- [数据库](docs/database/schema.md)
- [验证记录](docs/validation.md)

所有改动须更新测试、通过检查并创建 Git commit，遵循 AGENTS.md。
