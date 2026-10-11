import base64
import io
import secrets
from dataclasses import replace
from pathlib import Path
from pypdf import PdfWriter

from .. import __version__
from ..ai.generation import chapter_prompt, exam_prompt
from ..core.config import AIConfig
from ..database.repositories.workspace import SCHEMA_VERSION
from ..documents.service import has_text, read_pdf, validate_range
from ..export.obsidian import export_vault
from ..knowledge.service import topics
from ..notes.service import note_view, restore_version
from ..search.service import search_notes
from ..storage.paths import managed_path
from ..tasks.manager import TaskManager
from .protocol import reply, validate_request

# Required and optional fields are explicit; unknown fields never reach services.
PARAMS = {
 "workspace.get": (set(), set()), "onboarding.complete": (set(), set()),
 "documents.import": ({"path","kind"}, {"course","year"}),
 "documents.bookmarks": ({"document_id"}, set()),
 "chapters.create": ({"document_id","title","start_page","end_page"}, set()),
 "reader.page": ({"document_id","page"}, set()),
 "notes.save": ({"title","body","tags"}, {"note_id"}),
 "notes.search": (set(), {"query","topic"}), "notes.versions": ({"note_id"}, set()),
 "notes.restore": ({"note_id","version_id"}, set()),
 "settings.save": ({"config"}, {"api_key"}), "settings.delete_key": (set(), set()),
 "generation.prepare": ({"kind"}, {"chapter_id","document_ids","preference","secondary"}),
 "generation.start": ({"token"}, set()), "tasks.get": ({"task_id"}, set()),
 "export.obsidian": ({"destination"}, set()), "backup.create": ({"destination"}, set()),
}


def number(params, key):
    value = params[key]
    if type(value) is not int or value < 1:
        raise ValueError("记录标识或页码无效。")
    return value


def text(params, key, default=""):
    value = params.get(key, default)
    if not isinstance(value, str) or len(value) > 250000:
        raise ValueError("文本参数无效或过长。")
    return value


class Router:
    def __init__(self, workspace):
        self.workspace, self.db = workspace, workspace.db
        self.tasks = TaskManager()
        self.prepared = {}

    def handle(self, request):
        request_id = request.get("id", "") if isinstance(request, dict) else ""
        request_id = request_id if isinstance(request_id, str) and len(request_id) <= 80 else ""
        try:
            validate_request(request)
            method, params = request["method"], request["params"]
            required, optional = PARAMS[method]
            if not required <= params.keys() or not params.keys() <= required | optional:
                raise ValueError("请求参数缺失或包含未知字段。")
            if self.tasks.active() and method not in {"workspace.get", "tasks.get", "notes.search", "notes.versions", "reader.page", "notes.save"}:
                raise ValueError("生成任务正在运行，请完成后再执行这项操作。")
            return reply(request_id, self.dispatch(method, params))
        except Exception as error:
            return reply(request_id, error=error)

    def snapshot(self):
        documents = self.db.rows("SELECT id,title,kind,course,year,pages,status FROM documents ORDER BY id DESC")
        chapters = self.db.rows("SELECT id,document_id,title,start_page,end_page,text FROM chapters ORDER BY document_id,start_page,id")
        return {"version": __version__, "schema_version": SCHEMA_VERSION, "data_directory": str(self.workspace.directory),
                "onboarding_complete": self.db.setting("onboarding_complete", False),
                "documents": documents, "chapters": chapters, "notes": search_notes(self.db), "topics": topics(self.db),
                "config": self.workspace.config().to_dict(), "key_configured": self.workspace.keys.path.exists(), "spent": self.db.spent()}

    def dispatch(self, method, p):
        if method == "workspace.get":
            return self.snapshot()
        if method == "onboarding.complete":
            self.db.set_setting("onboarding_complete", True)
            return {"completed": True}
        if method == "documents.import":
            return {"document_id": self.workspace.documents.import_file(text(p,"path"), text(p,"kind"), text(p,"course"), text(p,"year"))}
        if method == "documents.bookmarks":
            return {"ranges": [{"title": t, "start_page": s, "end_page": e}
                               for t,s,e in self.workspace.documents.bookmark_ranges(number(p,"document_id"))]}
        if method == "chapters.create":
            return {"chapter_id": self.workspace.documents.create_chapter(number(p,"document_id"), text(p,"title"), number(p,"start_page"), number(p,"end_page"))}
        if method == "reader.page":
            document = self.db.get("documents", number(p,"document_id"))
            reader = read_pdf(managed_path(self.workspace.directory, document["path"]))
            page = number(p,"page")
            validate_range(page,page,len(reader.pages))
            writer = PdfWriter()
            writer.add_page(reader.pages[page-1])
            stream = io.BytesIO()
            writer.write(stream)
            if stream.tell() > 8*1024*1024:
                raise ValueError("当前页过大，暂不能内嵌预览。")
            return {"pdf_base64": base64.b64encode(stream.getvalue()).decode("ascii"), "page": page, "total": len(reader.pages)}
        if method == "notes.save":
            tags = p["tags"]
            if not isinstance(tags,list) or len(tags)>50 or any(not isinstance(tag,str) or len(tag)>100 for tag in tags):
                raise ValueError("知识主题格式无效。")
            note_id = number(p,"note_id") if p.get("note_id") is not None else None
            return {"note_id": self.db.save_note(text(p,"title"), text(p,"body"), tags=tags, note_id=note_id)}
        if method == "notes.search":
            return {"notes": search_notes(self.db,text(p,"query"),text(p,"topic"))}
        if method == "notes.versions":
            return {"versions": self.db.versions(number(p,"note_id"))}
        if method == "notes.restore":
            return {"note_id": restore_version(self.db,number(p,"note_id"),number(p,"version_id"))}
        if method == "settings.save":
            if not isinstance(p["config"],dict):
                raise ValueError("AI 配置格式无效。")
            try:
                config = AIConfig(**p["config"]).validate()
            except (TypeError, AttributeError):
                raise ValueError("AI 配置包含未知字段或无效类型。") from None
            key = text(p,"api_key").strip()
            if key:
                self.workspace.keys.save(key)
            self.db.set_setting("ai",config.to_dict())
            return {"saved": True, "key_configured": self.workspace.keys.path.exists()}
        if method == "settings.delete_key":
            self.workspace.keys.delete()
            return {"deleted": True}
        if method == "generation.prepare":
            return self.prepare(p)
        if method == "generation.start":
            token = text(p,"token")
            if token not in self.prepared:
                raise ValueError("预览已失效，请重新生成预览。")
            prepared = self.prepared.pop(token)
            def generate():
                result = self.workspace.ai.generate(prepared["config"],prepared["prompt"])
                note_id = None
                if prepared["kind"] != "connection":
                    note_id = self.db.save_note(prepared["title"],result.body,prepared["sources"],prepared["tags"],prepared["note_kind"])
                return {"note_id": note_id,"cached": result.cached,"amount": result.amount}
            return self.tasks.start(generate)
        if method == "tasks.get":
            return self.tasks.get(text(p,"task_id"))
        if method == "export.obsidian":
            return {"path": str(export_vault(self.db,text(p,"destination")))}
        if method == "backup.create":
            return {"path": str(self.workspace.backup(text(p,"destination")))}
        raise ValueError("未支持的操作。")

    def prepare(self,p):
        kind = text(p,"kind")
        secondary = p.get("secondary",False)
        if type(secondary) is not bool:
            raise ValueError("模型选择无效。")
        config = self.workspace.config().selected(secondary)
        preference = text(p,"preference")
        title, sources, tags, note_kind = "连接测试", [], [], "note"
        if kind == "chapter":
            chapter = self.db.get("chapters",number(p,"chapter_id"))
            document = self.db.get("documents",chapter["document_id"])
            if not has_text(chapter["text"]):
                raise ValueError("章节没有可读取的文字，请先进行 OCR。")
            prompt = chapter_prompt(chapter,document,preference)
            title = chapter["title"]
            sources = [f"{document['title']} / {title} / PDF 第 {chapter['start_page']}-{chapter['end_page']} 页"]
            tags = [document["course"]] if document["course"] else []
        elif kind == "exams":
            ids = p.get("document_ids")
            if not isinstance(ids,list) or not ids or len(ids)>20 or any(type(value) is not int or value<1 for value in ids):
                raise ValueError("请选择 1 到 20 份试卷。")
            documents = [self.db.get("documents",value) for value in dict.fromkeys(ids)]
            if any(d["kind"] != "exam" for d in documents):
                raise ValueError("分析材料必须是试卷。")
            courses = {d["course"] for d in documents if d["course"]}
            if len(courses)>1:
                raise ValueError("请选择同课程的试卷。")
            prompt = exam_prompt([(d,self.workspace.documents.exam_text(d["id"])) for d in documents],preference)
            title = f"{next(iter(courses),'试卷')} · 考点分析"
            sources = [f"{d['title']} / {d['year'] or '年份未提供'}" for d in documents]
            tags,note_kind = list(courses),"exam-report"
        elif kind == "connection":
            config = replace(config,max_output_tokens=128)
            prompt = "连接测试：请仅回复“连接成功”。"
        else:
            raise ValueError("未支持的生成任务。")
        estimate = self.workspace.ai.estimate(config,prompt)
        # One preview per session: obsolete previews cannot keep accumulating.
        self.prepared.clear()
        token = secrets.token_urlsafe(32)
        self.prepared[token] = {"config": config,"prompt": prompt,"kind":kind,"title":title,"sources":sources,"tags":tags,"note_kind":note_kind}
        return {"token":token,"prompt":prompt,"amount":estimate.amount,"cached":estimate.cached,"model":config.model,"endpoint":config.base_url}

    def close(self):
        self.tasks.close()
