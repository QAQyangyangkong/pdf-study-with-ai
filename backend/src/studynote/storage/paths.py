from pathlib import Path


def managed_path(directory, relative):
    root = Path(directory).resolve()
    result = (root / relative).resolve()
    if not result.is_relative_to(root):
        raise ValueError("资料路径超出工作区。")
    return result
