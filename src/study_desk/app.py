"""Native Windows UI. Slow work runs off the Tk event loop."""
import json
import queue
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import __version__
from .ai import chapter_prompt, exam_prompt
from .config import AIConfig
from .documents import has_text
from .export import export_vault


class StudyApp:
    def __init__(self, root, workspace):
        self.root, self.workspace = root, workspace
        self.db = workspace.db
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.events = queue.Queue()
        self.busy = False
        self.closed = False
        self.note_id = None
        self.saved_note = None
        self.preference = tk.StringVar(value="面向初学者，保留推导过程，用简短例子解释。")
        self.model_choice = tk.StringVar(value="主模型")
        root.title(f"Study Desk · AI 学习工作台 {__version__}")
        root.geometry("1180x800")
        root.minsize(980, 680)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", font=("Microsoft YaHei UI", 10), background="#f5f7fa")
        style.configure("TFrame", background="#f5f7fa")
        style.configure("TLabel", background="#f5f7fa", foreground="#243449")
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 23, "bold"))
        style.configure("Muted.TLabel", foreground="#66758a")
        style.configure("TButton", padding=(12, 7))
        style.configure("Accent.TButton", background="#22685a", foreground="white")
        style.map("Accent.TButton", background=[("active", "#185044")])
        style.configure("Treeview", rowheight=30, background="white", fieldbackground="white")
        style.configure("TNotebook.Tab", padding=(22, 10))
        self.build()
        self.refresh()
        self.poll_id = root.after(100, self.poll)
        root.protocol("WM_DELETE_WINDOW", self.close)

    def button(self, parent, text, command, accent=False):
        return ttk.Button(parent, text=text, style="Accent.TButton" if accent else "TButton",
                          command=lambda: self.safe(command))

    def safe(self, command):
        try:
            if self.busy:
                raise ValueError("当前任务正在处理，请等完成后再操作。")
            command()
        except Exception as error:
            self.show_error(error)

    def show_error(self, error):
        # Unexpected transport errors must not leak headers/keys into dialogs.
        text = str(error) if isinstance(error, (ValueError, RuntimeError)) else "处理失败，请检查文件、目录权限或配置后重试。"
        messagebox.showerror("未完成", text, parent=self.root)
        self.status.set(text)

    def build(self):
        outer = ttk.Frame(self.root, padding=24)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 18))
        ttk.Label(header, text="Study Desk", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="  把教材变成自己的知识体系", style="Muted.TLabel").pack(side="left", padx=12)
        self.button(header, "导出 Obsidian", self.export).pack(side="right")
        self.button(header, "备份数据", self.backup).pack(side="right", padx=8)
        self.summary = tk.StringVar()
        ttk.Label(outer, textvariable=self.summary, style="Muted.TLabel").pack(anchor="w", pady=(0, 12))
        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill="both", expand=True)
        self.library_tab, self.notes_tab, self.exams_tab, self.settings_tab = [ttk.Frame(self.tabs, padding=18) for _ in range(4)]
        for tab, title in zip((self.library_tab, self.notes_tab, self.exams_tab, self.settings_tab),
                              ("教材与章节", "笔记与知识", "试卷分析", "AI 设置")):
            self.tabs.add(tab, text=title)
        self.build_library()
        self.build_notes()
        self.build_exams()
        self.build_settings()
        self.status = tk.StringVar(value="准备就绪 · 文件与笔记保存在本机。只有确认生成时才发送文字材料。")
        ttk.Label(outer, textvariable=self.status, style="Muted.TLabel", wraplength=1080).pack(anchor="w", pady=(12, 0))

    def tree(self, parent, columns, widths, selectmode="browse"):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=tuple(columns), show="headings", selectmode=selectmode)
        for name, width in zip(columns, widths):
            tree.heading(name, text=name)
            tree.column(name, width=width, minwidth=50)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)
        return tree

    def text_area(self, parent, height=12, readonly=False):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True, pady=8)
        text = tk.Text(frame, wrap="word", undo=not readonly, height=height, font=("Microsoft YaHei UI", 10),
                       bg="white", fg="#26374b", relief="flat", padx=14, pady=12)
        scroll = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(fill="both", expand=True)
        if readonly:
            text.configure(state="disabled")
        return text

    def set_text(self, widget, text, readonly=False):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        if readonly:
            widget.configure(state="disabled")

    def ai_controls(self, parent):
        ttk.Label(parent, text="学习偏好").pack(side="left")
        ttk.Entry(parent, textvariable=self.preference).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Combobox(parent, textvariable=self.model_choice, values=("主模型", "第二模型"),
                     state="readonly", width=9).pack(side="right")

    def build_library(self):
        bar = ttk.Frame(self.library_tab)
        bar.pack(fill="x", pady=(0, 12))
        self.button(bar, "＋ 导入教材 PDF", self.import_textbook, True).pack(side="left")
        self.button(bar, "查看书签建议", self.bookmarks).pack(side="left", padx=8)
        ttk.Label(bar, text="页码使用 PDF 实际页码，包含封面与目录。", style="Muted.TLabel").pack(side="right")
        pane = ttk.Panedwindow(self.library_tab, orient="horizontal")
        pane.pack(fill="both", expand=True)
        left, right = ttk.Frame(pane), ttk.Frame(pane)
        pane.add(left, weight=2)
        pane.add(right, weight=3)
        ttk.Label(left, text="我的教材").pack(anchor="w")
        self.books = self.tree(left, ("教材", "课程", "页数"), (210, 100, 50))
        self.books.bind("<<TreeviewSelect>>", lambda event: self.refresh_chapters())
        ttk.Label(left, text="已拆分章节").pack(anchor="w", pady=(12, 0))
        self.chapters = self.tree(left, ("章节", "页码"), (290, 80))
        self.chapters.bind("<<TreeviewSelect>>", lambda event: self.preview_chapter())
        ttk.Label(right, text="创建章节").pack(anchor="w")
        fields = ttk.Frame(right)
        fields.pack(fill="x", pady=8)
        self.chapter_title = tk.StringVar(value="第一章")
        self.start_page, self.end_page = tk.StringVar(value="1"), tk.StringVar(value="10")
        for name, variable, width in (("名称", self.chapter_title, 16), ("起始页", self.start_page, 5), ("结束页", self.end_page, 5)):
            ttk.Label(fields, text=name).pack(side="left", padx=(0, 4))
            ttk.Entry(fields, textvariable=variable, width=width).pack(side="left", padx=(0, 8))
        self.button(right, "拆分并提取文字", self.split_chapter, True).pack(anchor="w", pady=(0, 4))
        ttk.Label(right, text="章节文字预览 · 扫描件需先进行 OCR", style="Muted.TLabel").pack(anchor="w", pady=(10, 0))
        self.chapter_preview = self.text_area(right, readonly=True)
        preference_bar = ttk.Frame(right)
        preference_bar.pack(fill="x", pady=8)
        self.ai_controls(preference_bar)
        self.button(right, "生成所选章节笔记", self.generate_chapter, True).pack(anchor="e")

    def build_notes(self):
        pane = ttk.Panedwindow(self.notes_tab, orient="horizontal")
        pane.pack(fill="both", expand=True)
        left, right = ttk.Frame(pane), ttk.Frame(pane)
        pane.add(left, weight=1)
        pane.add(right, weight=3)
        self.search = tk.StringVar()
        ttk.Label(left, text="搜索标题或正文").pack(anchor="w")
        entry = ttk.Entry(left, textvariable=self.search)
        entry.pack(fill="x", pady=6)
        entry.bind("<Return>", lambda event: self.refresh_notes())
        self.topic_filter = tk.StringVar()
        ttk.Label(left, text="按知识主题查看跨教材笔记").pack(anchor="w", pady=(6, 0))
        self.topic_box = ttk.Combobox(left, textvariable=self.topic_filter, state="readonly")
        self.topic_box.pack(fill="x", pady=6)
        self.topic_box.bind("<<ComboboxSelected>>", lambda event: self.refresh_notes())
        self.note_list = self.tree(left, ("笔记", "类型"), (240, 60))
        self.note_list.bind("<Double-1>", lambda event: self.safe(self.open_selected_note))
        bar = ttk.Frame(left)
        bar.pack(fill="x", pady=8)
        self.button(bar, "打开", self.open_selected_note).pack(side="left")
        self.button(bar, "新建", self.new_note).pack(side="left", padx=6)
        self.note_title = tk.StringVar()
        self.note_tags = tk.StringVar()
        ttk.Label(right, text="笔记标题").pack(anchor="w")
        ttk.Entry(right, textvariable=self.note_title).pack(fill="x", pady=6)
        ttk.Label(right, text="知识主题（用逗号分隔，相同主题自动连接不同教材）", style="Muted.TLabel").pack(anchor="w")
        ttk.Entry(right, textvariable=self.note_tags).pack(fill="x", pady=6)
        self.note_body = self.text_area(right)
        self.note_sources = tk.StringVar(value="手动笔记")
        ttk.Label(right, textvariable=self.note_sources, style="Muted.TLabel", wraplength=700).pack(anchor="w")
        self.button(right, "保存笔记", self.save_note, True).pack(anchor="e", pady=8)

    def build_exams(self):
        bar = ttk.Frame(self.exams_tab)
        bar.pack(fill="x", pady=(0, 12))
        self.exam_course = tk.StringVar()
        self.exam_year = tk.StringVar()
        for name, variable, width in (("课程", self.exam_course, 22), ("年份", self.exam_year, 8)):
            ttk.Label(bar, text=name).pack(side="left", padx=(0, 5))
            ttk.Entry(bar, textvariable=variable, width=width).pack(side="left", padx=(0, 12))
        self.button(bar, "＋ 导入试卷", self.import_exam, True).pack(side="left")
        ttk.Label(self.exams_tab, text="支持文字 PDF、DOCX、UTF-8 TXT。图片可登记，OCR 尚未接入。按 Ctrl 多选同课程的历年试卷。",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 10))
        self.exams = self.tree(self.exams_tab, ("试卷", "课程", "年份", "状态"), (400, 180, 80, 160), "extended")
        bar = ttk.Frame(self.exams_tab)
        bar.pack(fill="x", pady=12)
        self.ai_controls(bar)
        self.button(self.exams_tab, "分析所选试卷并保存报告", self.analyze_exams, True).pack(anchor="e")

    def build_settings(self):
        ttk.Label(self.settings_tab, text="首次使用：确认模型与单价 → 保存自己的 API Key → 验证连接。").pack(anchor="w")
        ttk.Label(self.settings_tab, text="金额单位均为 USD；单价按每百万 token 填写。默认值核对于 2026-10-11，使用前请核对服务商价格。",
                  style="Muted.TLabel").pack(anchor="w", pady=(5, 12))
        form = ttk.Frame(self.settings_tab)
        form.pack(fill="x")
        config = self.workspace.config()
        labels = [("base_url", "API 地址"), ("model", "主模型（默认推荐 DeepSeek Flash）"),
                  ("secondary_model", "第二模型（可留空，手动填写）"),
                  ("daily_budget", "每日预算 / USD"), ("input_price", "主模型输入单价"),
                  ("output_price", "主模型输出单价"), ("secondary_input_price", "第二模型输入单价"),
                  ("secondary_output_price", "第二模型输出单价"), ("max_output_tokens", "最大输出 token")]
        self.config_vars = {}
        for row, (field, label) in enumerate(labels):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=(0, 20), pady=4)
            variable = tk.StringVar(value=str(getattr(config, field)))
            self.config_vars[field] = variable
            ttk.Entry(form, textvariable=variable, width=58).grid(row=row, column=1, sticky="ew", pady=4)
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="API Key（留空保留已保存密钥）").grid(row=len(labels), column=0, sticky="w", pady=4)
        self.api_key = tk.StringVar()
        ttk.Entry(form, textvariable=self.api_key, show="●").grid(row=len(labels), column=1, sticky="ew", pady=4)
        ttk.Label(self.settings_tab, text="密钥由 Windows 当前账号加密，不写入数据库、导出或备份。更换电脑后需要重新配置。",
                  style="Muted.TLabel", wraplength=990).pack(anchor="w", pady=10)
        bar = ttk.Frame(self.settings_tab)
        bar.pack(fill="x")
        self.button(bar, "保存配置", self.save_config, True).pack(side="left")
        self.button(bar, "验证已保存的主模型", self.test_connection).pack(side="left", padx=8)
        self.button(bar, "删除已保存密钥", self.delete_key).pack(side="left")
        ttk.Label(self.settings_tab, text="预算是本地费用估算，实际扣费以服务商账单为准。失败请求保留预算占用，避免重复调用。\n"
                  "安装包覆盖升级前建议备份数据；此版本尚未接入自动更新服务器。",
                  style="Muted.TLabel", wraplength=990).pack(anchor="w", pady=16)

    def selected_id(self, tree):
        selection = tree.selection()
        if not selection:
            raise ValueError("请先选择一条记录。")
        return int(selection[0])

    def fill_tree(self, tree, rows, fields):
        selected = tree.selection()
        tree.delete(*tree.get_children())
        for row in rows:
            tree.insert("", "end", iid=str(row["id"]), values=[row[field] for field in fields])
        for item in selected:
            if tree.exists(item):
                tree.selection_add(item)

    def refresh(self):
        self.fill_tree(self.books, self.db.rows("SELECT * FROM documents WHERE kind='textbook' ORDER BY id DESC"),
                       ("title", "course", "pages"))
        self.fill_tree(self.exams, self.db.rows("SELECT * FROM documents WHERE kind='exam' ORDER BY year DESC,id DESC"),
                       ("title", "course", "year", "status"))
        self.refresh_chapters()
        self.refresh_notes()
        counts = self.db.rows("SELECT (SELECT COUNT(*) FROM documents WHERE kind='textbook') books, "
                              "(SELECT COUNT(*) FROM chapters) chapters, (SELECT COUNT(*) FROM notes) notes")[0]
        self.summary.set(f"{counts['books']} 本教材   ·   {counts['chapters']} 个章节   ·   {counts['notes']} 篇笔记"
                         f"     |     今日费用记录 ${self.db.spent():.4f} / ${self.workspace.config().daily_budget:.2f}")

    def refresh_chapters(self):
        book_id = int(self.books.selection()[0]) if self.books.selection() else None
        rows = self.db.rows("SELECT *, start_page || '-' || end_page AS range FROM chapters WHERE document_id=? ORDER BY start_page,id",
                            (book_id,))
        self.fill_tree(self.chapters, rows, ("title", "range"))
        self.preview_chapter()

    def refresh_notes(self):
        topics = [""] + [row["name"] for row in self.db.rows(
            "SELECT name FROM topics WHERE EXISTS (SELECT 1 FROM note_topics WHERE topic_id=topics.id) ORDER BY name")]
        self.topic_box.configure(values=topics)
        if self.topic_filter.get() not in topics:
            self.topic_filter.set("")
        rows = self.db.notes(self.search.get(), self.topic_filter.get())
        for row in rows:
            row["display_kind"] = "考点报告" if row["kind"] == "exam-report" else "学习笔记"
        self.fill_tree(self.note_list, rows, ("title", "display_kind"))

    def preview_chapter(self):
        if self.chapters.selection():
            chapter = self.db.get("chapters", self.selected_id(self.chapters))
            text = chapter["text"] if has_text(chapter["text"]) else "未提取到文字：这可能是扫描件，需要 OCR。拆分的 PDF 已保存。"
            self.set_text(self.chapter_preview, text, True)
        else:
            self.set_text(self.chapter_preview, "选择教材，填写页码，拆分后在这里核对提取的文字。", True)

    def run_task(self, label, function, success):
        if self.busy:
            raise ValueError("当前任务尚未完成。")
        self.busy = True
        self.status.set(label + "…")
        def work():
            try:
                self.events.put((success, function(), None))
            except Exception as error:
                self.events.put((success, None, error))
        self.executor.submit(work)

    def poll(self):
        try:
            success, result, error = self.events.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            if error:
                self.show_error(error)
            else:
                try:
                    success(result)
                except Exception as callback_error:
                    self.show_error(callback_error)
            self.refresh()
        if not self.closed:
            self.poll_id = self.root.after(100, self.poll)

    def import_textbook(self):
        paths = filedialog.askopenfilenames(parent=self.root, title="选择教材", filetypes=[("PDF", "*.pdf")])
        if not paths:
            return
        course = simpledialog.askstring("课程", "为这批教材填写课程（可留空）", parent=self.root)
        if course is None:
            return
        self.run_task("正在导入教材", lambda: [self.workspace.documents.import_file(path, course=course) for path in paths],
                      lambda ids: self.status.set(f"导入完成，共 {len(ids)} 本；同一课程的相同文件会复用已有记录。"))

    def split_chapter(self):
        book_id = self.selected_id(self.books)
        title, start, end = self.chapter_title.get(), int(self.start_page.get()), int(self.end_page.get())
        def done(chapter_id):
            self.refresh_chapters()
            self.chapters.selection_set(str(chapter_id))
            self.preview_chapter()
            self.status.set("章节已拆分并保存；请核对文字后生成笔记。")
        self.run_task("正在拆分章节", lambda: self.workspace.documents.create_chapter(book_id, title, start, end), done)

    def bookmarks(self):
        book_id = self.selected_id(self.books)
        def show(ranges):
            if not ranges:
                messagebox.showinfo("没有书签", "该 PDF 没有顶层书签，请手动填写章节页码。", parent=self.root)
                return
            dialog = tk.Toplevel(self.root)
            dialog.title("书签建议 · 选择后可修改页码")
            dialog.geometry("620x430")
            listing = tk.Listbox(dialog, font=("Microsoft YaHei UI", 11))
            listing.pack(fill="both", expand=True, padx=18, pady=18)
            for title, start, end in ranges:
                listing.insert("end", f"{title}  ·  {start}-{end}")
            def choose():
                if listing.curselection():
                    title, start, end = ranges[listing.curselection()[0]]
                    self.chapter_title.set(title)
                    self.start_page.set(str(start))
                    self.end_page.set(str(end))
                    dialog.destroy()
            ttk.Button(dialog, text="使用选定范围", command=choose).pack(pady=(0, 18))
            dialog.transient(self.root)
            dialog.grab_set()
        self.run_task("正在读取书签", lambda: self.workspace.documents.bookmark_ranges(book_id), show)

    def selected_config(self):
        return self.workspace.config().selected(self.model_choice.get() == "第二模型")

    def confirm_request(self, config, prompt, complete):
        estimate = self.workspace.ai.estimate(config, prompt)
        dialog = tk.Toplevel(self.root)
        dialog.title("确认 AI 请求")
        dialog.geometry("760x570")
        container = ttk.Frame(dialog, padding=18)
        container.pack(fill="both", expand=True)
        description = "命中本地缓存，本次不联网。" if estimate.cached else (
            f"将以下文字发送至 {config.base_url}\n模型：{config.model} · 费用保守估算 ${estimate.amount:.5f} USD")
        ttk.Label(container, text=description, wraplength=710).pack(anchor="w")
        preview = self.text_area(container, readonly=True)
        self.set_text(preview, prompt, True)
        ttk.Label(container, text="只发送文字和学习偏好；请检查材料、页码与隐私内容。", style="Muted.TLabel").pack(anchor="w")
        bar = ttk.Frame(container)
        bar.pack(fill="x", pady=(12, 0))
        def send():
            dialog.destroy()
            self.safe(lambda: self.run_task("正在生成（网络请求最多等待 60 秒）",
                lambda: self.workspace.ai.generate(config, prompt), complete))
        ttk.Button(bar, text="使用缓存" if estimate.cached else "确认生成", command=send).pack(side="right")
        ttk.Button(bar, text="取消", command=dialog.destroy).pack(side="right", padx=8)
        dialog.transient(self.root)
        dialog.grab_set()

    def generate_chapter(self):
        chapter = self.db.get("chapters", self.selected_id(self.chapters))
        if not has_text(chapter["text"]):
            raise ValueError("章节没有可读取的文字，请先进行 OCR。")
        document = self.db.get("documents", chapter["document_id"])
        prompt = chapter_prompt(chapter, document, self.preference.get())
        source = f"{document['title']} / {chapter['title']} / PDF 第 {chapter['start_page']}-{chapter['end_page']} 页"
        def complete(result):
            note_id = self.db.save_note(chapter["title"], result.body, [source], [document["course"]] if document["course"] else [])
            self.show_generated(note_id, result)
        self.confirm_request(self.selected_config(), prompt, complete)

    def editor_state(self):
        return self.note_title.get(), self.note_body.get("1.0", "end-1c"), self.note_tags.get()

    def leave_editor(self):
        current = self.editor_state()
        dirty = current != self.saved_note if self.saved_note is not None else any(part.strip() for part in current)
        if not dirty:
            return True
        answer = messagebox.askyesnocancel("保存修改", "当前笔记有未保存修改，是否先保存？", parent=self.root)
        if answer is None:
            return False
        if answer:
            self.save_note()
        return True

    def load_note(self, note_id):
        note = self.db.get("notes", note_id)
        self.note_id = note_id
        self.note_title.set(note["title"])
        self.note_tags.set(", ".join(self.db.tags(note_id)))
        self.set_text(self.note_body, note["body"])
        self.note_sources.set("来源：" + "；".join(json.loads(note["sources"])) if json.loads(note["sources"]) else "手动笔记")
        self.saved_note = self.editor_state()

    def open_selected_note(self):
        note_id = self.selected_id(self.note_list)
        if self.leave_editor():
            self.load_note(note_id)

    def new_note(self):
        if self.leave_editor():
            self.note_id = None
            self.note_title.set("")
            self.note_tags.set("")
            self.set_text(self.note_body, "")
            self.note_sources.set("手动笔记")
            self.saved_note = self.editor_state()

    def save_note(self):
        title, body, tags = self.editor_state()
        self.note_id = self.db.save_note(title, body, tags=tags.replace("，", ",").split(","), note_id=self.note_id)
        self.saved_note = self.editor_state()
        self.status.set("笔记已保存。相同知识主题下可以查看不同教材的笔记。")
        self.refresh()

    def show_generated(self, note_id, result):
        if self.leave_editor():
            self.load_note(note_id)
            self.tabs.select(self.notes_tab)
        self.status.set("结果已保存到笔记库。" + ("使用本地缓存，本次没有费用。" if result.cached else f"本次费用记录 ${result.amount:.5f} USD。"))

    def import_exam(self):
        paths = filedialog.askopenfilenames(parent=self.root, title="选择试卷",
            filetypes=[("试卷", "*.pdf *.docx *.txt *.png *.jpg *.jpeg"), ("所有文件", "*.*")])
        if not paths:
            return
        course, year = self.exam_course.get(), self.exam_year.get()
        if year and (not year.isdigit() or len(year) != 4):
            raise ValueError("年份请填写四位数字，或留空。")
        self.run_task("正在导入试卷", lambda: [self.workspace.documents.import_file(path, "exam", course, year) for path in paths],
                      lambda ids: self.status.set(f"已登记 {len(ids)} 份试卷。"))

    def analyze_exams(self):
        ids = [int(item) for item in self.exams.selection()]
        if not ids:
            raise ValueError("请先选择要分析的试卷，可按 Ctrl 多选。")
        documents = [self.db.get("documents", item) for item in ids]
        courses = {document["course"] for document in documents if document["course"]}
        if len(courses) > 1:
            raise ValueError("请选择同一课程的试卷进行考情分析。")
        config, preference = self.selected_config(), self.preference.get()
        def prepare():
            return [(document, self.workspace.documents.exam_text(document["id"])) for document in documents]
        def ready(materials):
            prompt = exam_prompt(materials, preference)
            sources = [f"{document['title']} / 年份 {document['year'] or '未提供'}" for document in documents]
            def complete(result):
                title = f"{next(iter(courses), '试卷')} · {len(documents)} 份试卷考点分析"
                note_id = self.db.save_note(title, result.body, sources, list(courses), "exam-report")
                self.show_generated(note_id, result)
            self.confirm_request(config, prompt, complete)
        self.run_task("正在提取试卷文字", prepare, ready)

    def save_config(self):
        values = {field: var.get().strip() for field, var in self.config_vars.items()}
        for field in ("daily_budget", "input_price", "output_price", "secondary_input_price", "secondary_output_price"):
            values[field] = float(values[field])
        values["max_output_tokens"] = int(values["max_output_tokens"])
        config = AIConfig(**values).validate()
        if self.api_key.get().strip():
            self.workspace.keys.save(self.api_key.get())
            self.api_key.set("")
        self.db.set_setting("ai", config.to_dict())
        self.status.set("配置已保存。更换模型后请先验证连接，并核对对应单价。")
        self.refresh()

    def test_connection(self):
        config = replace(self.workspace.config(), max_output_tokens=128)
        self.confirm_request(config, "连接测试：请仅回复“连接成功”。", lambda result: self.status.set(
            "连接成功，模型可返回文本；此验证不代表 OCR、图片或结构化输出能力。"))

    def delete_key(self):
        if messagebox.askyesno("删除密钥", "删除本机已保存的 API Key？", parent=self.root):
            self.workspace.keys.delete()
            self.api_key.set("")
            self.status.set("已删除密钥。")

    def export(self):
        if not self.leave_editor():
            return
        destination = filedialog.askdirectory(parent=self.root, title="选择导出位置")
        if destination:
            self.run_task("正在导出 Markdown", lambda: export_vault(self.db, destination),
                          lambda path: messagebox.showinfo("导出完成", f"可在 Obsidian 打开的文件夹：\n{path}", parent=self.root))

    def backup(self):
        if not self.leave_editor():
            return
        destination = filedialog.asksaveasfilename(parent=self.root, title="备份本地资料", defaultextension=".zip",
            initialfile="StudyDesk-backup.zip", filetypes=[("ZIP", "*.zip")])
        if destination:
            self.run_task("正在备份资料", lambda: self.workspace.backup(destination),
                          lambda path: messagebox.showinfo("备份完成", f"数据库、教材与章节已备份：\n{path}\nAPI Key 不包含在备份中。", parent=self.root))

    def close(self):
        if self.busy:
            messagebox.showinfo("任务进行中", "请等待当前任务完成后关闭，避免中断保存。", parent=self.root)
            return
        try:
            if not self.leave_editor():
                return
        except Exception as error:
            self.show_error(error)
            return
        self.closed = True
        self.root.after_cancel(self.poll_id)
        self.executor.shutdown(wait=False)
        self.root.destroy()
