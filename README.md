# Study Desk · AI 学习工作台

独立 Windows 桌面软件的第一版项目雏形。以本地文件、SQLite 和原生桌面界面打通教材到笔记的流程，支持导出到 Obsidian。

引用的「MVP功能规划」聊天中，用户需求可以读取，但助手的项目设计正文只返回内容占位符。因此本版本依据已读取需求构建；技术栈与阶段划分是本次实现的假设，见 [架构与范围](docs/architecture.md)。

## 已可使用

- 导入 PDF 教材，按文件内容去重，复制到本地工作区。
- 查看顶层 PDF 书签建议；手动填写章节页码，生成独立 PDF 并提取带原始页码的文字。
- 配置自己的 DeepSeek API Key、主模型和可选第二模型，验证文本连接。
- 修改学习偏好；预览发送材料及费用后生成笔记，相同请求命中缓存时不再调用 API。
- 编辑和搜索 Markdown 笔记，用共同知识主题关联不同教材，保留材料来源。
- 导入历年文字 PDF、DOCX、UTF-8 TXT 试卷，多选同课程材料生成考点分析报告。
- 登记图片试卷并提示需要 OCR；扫描 PDF 可以拆分，生成笔记前会检查有无文字。
- 导出 Markdown 笔记、知识主题索引和 Obsidian 双链；备份数据库与教材文件。

## 在这台电脑上启动

双击项目根目录的 `run.bat`。本次已创建 `.venv` 并安装运行依赖。

打包后可运行 `dist\StudyDesk\StudyDesk.exe`。分享时发送整个 `StudyDesk` 文件夹，或 `dist\StudyDesk-0.1.0-windows-x64.zip`，接收者不需要安装 Python。

首次使用建议：

1. 在「教材与章节」导入教材，填写课程。
2. 选择教材，填写章节名称与 **PDF 实际页码**（封面也计入），拆分并核对文字。
3. 在「AI 设置」填写自己的 Key，核对模型与单价，保存并验证连接。
4. 回到章节，设置学习偏好，预览材料后确认生成。
5. 在「笔记与知识」编辑正文，为不同教材的相关笔记填写相同主题，保存并导出。
6. 在「试卷分析」按年份分批导入试卷，按 Ctrl 多选同课程试卷生成报告。

未配置 Key 时，导入、拆分、手动笔记、知识主题、备份与导出都可离线使用。开发测试通过模拟接口验证完整流程，没有向服务商上传你的教材或调用付费 AI。

## 开发环境

Windows 10/11 x64，Python 3.11 或更新版本（需含 Tkinter）。本次验证使用 Python 3.14。

```powershell
$env:PYTHONUTF8 = '1'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run.bat
```

如本机 Python 的 `ensurepip` 不可用，可用 uv 安装到虚拟环境：

```powershell
uv --cache-dir .cache\uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

运行测试及源码启动验证：

```powershell
.\scripts\check.ps1
```

构建便携版并验证打包后的界面启动：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\scripts\build.ps1
```

安装 Inno Setup 6 后，可运行 `.\scripts\build.ps1 -Installer` 生成安装包。安装脚本已经提供；是否实际构建见 [验证记录](docs/validation.md)。

## 数据、密钥与费用

默认数据目录为 `%LOCALAPPDATA%\StudyDesk`，与程序安装目录分开。可通过 `run.bat --data-dir "D:\my-study-data"` 指定目录。章节 PDF 存在数据目录的 `chapters` 子目录，原始文件保留不变。

Key 使用 [Windows DPAPI](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata) 按当前 Windows 账号加密，不存入 SQLite、不回显、不写日志，也不进入备份或 Markdown 导出。迁移到另一台电脑时重新填写自己的 Key。备份包含教材、章节、笔记、配置与费用记录，请按个人资料保存。

DeepSeek 接口、默认模型与单价参考 [官方接口说明](https://api-docs.deepseek.com/) 和 [官方价格表](https://api-docs.deepseek.com/quick_start/pricing/)，核对日期为 **2026-10-11**。当前默认主模型 `deepseek-flash`，主模型估算使用高峰缓存未命中价格（输入 $0.30、输出 $1.20 / 百万 token）；第二模型价格字段默认对应 `deepseek-v4-pro`。选用其他模型时须同时调整对应价格。

每天预算默认为 **$1.00 USD**；不是人民币。费用预估用 UTF-8 字节数加余量估计输入 token，并预留最大输出。成功请求按返回 token 用量和配置价格记账；无用量或失败请求保留估算。价格变化、服务商 tokenizer、请求协议和其他客户端消费会造成偏差，本地预算不是服务商账户的硬性扣费上限。没有自动重试；缓存只保存有效完整文本。

## 当前边界

OCR、图片理解、旧版 `.doc`、向量检索、自动跨教材概念合并、大章节分层总结、笔记对话式修订、联网自动更新尚未实现。图片仅登记；扫描件需要外部 OCR；单次材料超过 16000 字符会要求拆小，不静默截断。自动更新与数据库迁移的后续设计见架构文档。

当前只有人工主题关联，试卷频次报告由 AI 生成并保留材料来源，需核对原卷。软件只验证模型的文本响应能力。此版本是可运行雏形，尚未进行正式代码签名与公开发布验收。
