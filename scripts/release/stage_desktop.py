"""Stage only desktop binaries and beginner instructions, without project data."""
import argparse
import hashlib
from pathlib import Path
import shutil
import sys
import tempfile


BEGINNER_HEADING = "## 普通用户使用教程"
DEVELOPER_HEADING = "## 开发者说明：环境与启动"


def _file(path, label):
    path = Path(path).resolve()
    if not path.is_file():
        raise ValueError(f"缺少{label}：{path}")
    return path


def _output(path):
    path = Path(path).resolve()
    if path.exists() and not path.is_dir():
        raise ValueError(f"发布位置必须是文件夹：{path}")
    return path


def release_directory(root, output=None):
    """Keep release files under the project, resolving traversal and links."""
    root = Path(root).resolve()
    output = (Path(output) if output else root / "StudyNote").resolve()
    if output == root or not output.is_relative_to(root):
        raise ValueError("发布目录必须位于项目文件夹内的子目录。")
    return _output(output)


def _hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.digest()


def _same_bytes(first, second):
    return first.stat().st_size == second.stat().st_size and _hash(first) == _hash(second)


def _temporary(output):
    with tempfile.NamedTemporaryFile(prefix=".studynote-stage-", suffix=".tmp", dir=output, delete=False) as file:
        return Path(file.name)


def _stage_copy(source, output):
    temporary = _temporary(output)
    try:
        shutil.copyfile(source, temporary)
        if not _same_bytes(source, temporary):
            raise RuntimeError(f"复制校验失败，原文件保留：{source}")
        return temporary
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _guide(readme):
    text = readme.read_text(encoding="utf-8-sig")
    start = text.find(BEGINNER_HEADING)
    end = text.find(DEVELOPER_HEADING)
    if start < 0 or end <= start:
        raise ValueError("README 缺少普通用户教程或开发者说明分界，未复制发布文件。")
    return "# StudyNote 使用说明\n\n" + text[start:end].strip() + "\n"


def stage_portable(source, output, readme):
    source = Path(source).resolve()
    binaries = (
        (_file(source / "studynote-desktop.exe", "桌面程序"), "StudyNote.exe"),
        (_file(source / "studynote-backend.exe", "后台程序"), "studynote-backend.exe"),
    )
    instructions = _guide(_file(readme, "README 使用说明"))
    output = _output(output)
    for original, name in binaries:
        if original == (output / name).resolve():
            raise ValueError("发布目录必须与构建程序所在目录分开，原文件不会移动或删除。")
    output.mkdir(parents=True, exist_ok=True)
    staged = []
    try:
        # Prepare the whole set before publishing the first executable. Missing
        # inputs or a failed copy cannot produce a new partial desktop bundle.
        for original, name in binaries:
            staged.append((_stage_copy(original, output), output / name))
        guide = _temporary(output)
        staged.append((guide, output / "使用说明.txt"))
        guide.write_text(instructions, encoding="utf-8-sig")
        for temporary, destination in staged:
            temporary.replace(destination)
    finally:
        for temporary, _ in staged:
            temporary.unlink(missing_ok=True)
    return (output / "StudyNote.exe").resolve()


def stage_installer(source, output):
    source = _file(source, "安装包")
    if source.suffix.lower() != ".exe":
        raise ValueError("安装包必须是 .exe 文件，原文件保留。")
    output = _output(output)
    destination = output / source.name
    if source == destination.resolve():
        raise ValueError("安装包已经位于发布目录，不能删除唯一的原文件。")
    output.mkdir(parents=True, exist_ok=True)
    temporary = _stage_copy(source, output)
    try:
        temporary.replace(destination)
        if not _same_bytes(source, destination):
            raise RuntimeError("安装包复制校验失败，原文件保留。")
        # Delete this one generated input file only after the published copy is
        # verified. Never remove/move the source directory or unrelated files.
        source.unlink()
    finally:
        temporary.unlink(missing_ok=True)
    return destination.resolve()


def verify_portable(desktop, backend, output):
    """Require the exact installer inputs to match the tested standalone files."""
    output = _output(output)
    for source, name in ((desktop, "StudyNote.exe"), (backend, "studynote-backend.exe")):
        original = _file(source, "安装包输入程序")
        delivered = _file(output / name, "直接启动程序")
        if not _same_bytes(original, delivered):
            raise RuntimeError(f"安装包输入与已验证的 {name} 不一致，请先重新生成直接启动版。")
    return (output / "StudyNote.exe").resolve()


def main(argv=None):
    parser = argparse.ArgumentParser(description="整理 StudyNote 独立程序与安装包")
    commands = parser.add_subparsers(dest="command", required=True)
    directory = commands.add_parser("directory", help="核对发布目录位于项目文件夹内")
    directory.add_argument("--root", required=True)
    directory.add_argument("--output")
    portable = commands.add_parser("portable", help="复制独立程序与普通用户使用说明")
    portable.add_argument("--source", required=True)
    portable.add_argument("--output", required=True)
    portable.add_argument("--readme", required=True)
    installer = commands.add_parser("installer", help="校验并转移生成的安装包文件")
    installer.add_argument("--source", required=True)
    installer.add_argument("--output", required=True)
    verify = commands.add_parser("verify", help="核对安装包输入与已验证的直接启动程序")
    verify.add_argument("--desktop", required=True)
    verify.add_argument("--backend", required=True)
    verify.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "directory":
            result = release_directory(args.root, args.output)
        elif args.command == "portable":
            result = stage_portable(args.source, args.output, args.readme)
        elif args.command == "installer":
            result = stage_installer(args.source, args.output)
        else:
            result = verify_portable(args.desktop, args.backend, args.output)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"发布失败：{error}", file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
