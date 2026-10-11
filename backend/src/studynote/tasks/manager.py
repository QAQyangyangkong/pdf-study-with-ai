from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import uuid


class TaskManager:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.lock = Lock()
        self.tasks = {}

    def start(self, function):
        task_id = uuid.uuid4().hex
        with self.lock:
            if any(task["status"] in {"queued", "running"} for task in self.tasks.values()):
                raise ValueError("上一项生成任务尚未完成，请等完成后再试。")
            # Keep the latest 100 tasks to bound session memory.
            if len(self.tasks) >= 100:
                self.tasks.pop(next(iter(self.tasks)))
            self.tasks[task_id] = {"id": task_id, "status": "queued"}
        def run():
            with self.lock:
                self.tasks[task_id]["status"] = "running"
            try:
                result = function()
                with self.lock:
                    self.tasks[task_id].update(status="completed", result=result)
            except Exception as error:
                with self.lock:
                    self.tasks[task_id].update(status="failed", error=str(error) if isinstance(error, (ValueError, RuntimeError)) else "生成失败，请检查配置后重试。")
        self.executor.submit(run)
        return {"task_id": task_id}

    def get(self, task_id):
        with self.lock:
            if task_id not in self.tasks:
                raise ValueError("任务不存在，程序可能已经重新启动。")
            return dict(self.tasks[task_id])

    def active(self):
        with self.lock:
            return any(task["status"] in {"queued", "running"} for task in self.tasks.values())

    def close(self):
        self.executor.shutdown(wait=True)
