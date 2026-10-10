"""Entry point for source runs and the packaged application."""
import argparse
import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from . import __version__
from .app import StudyApp
from .config import default_data_dir
from .workspace import Workspace


def main():
    parser = argparse.ArgumentParser(description="Study Desk desktop learning workspace")
    parser.add_argument("--data-dir", type=Path, help="Override local data directory")
    parser.add_argument("--smoke-test", action="store_true", help="Initialize and verify UI, then exit")
    parser.add_argument("--report", type=Path, help="Smoke-test report destination")
    arguments = parser.parse_args()
    root = tk.Tk()
    try:
        workspace = Workspace(arguments.data_dir or default_data_dir())
        app = StudyApp(root, workspace)
        if arguments.smoke_test:
            root.update()
            assert len(app.tabs.tabs()) == 4
            report = {"version": __version__, "tabs": 4, "database": str(workspace.db.path), "ok": True}
            if arguments.report:
                arguments.report.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
            app.close()
            return
        root.mainloop()
    except Exception:
        root.withdraw()
        if arguments.smoke_test:
            root.destroy()
            raise
        messagebox.showerror("启动失败", "无法打开工作区，请检查数据目录权限或备份后恢复数据库。", parent=root)
        root.destroy()
        raise


if __name__ == "__main__":
    main()
