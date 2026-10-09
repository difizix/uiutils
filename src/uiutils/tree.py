"""Nested folder tree of relative paths, for tree browsers; free of streamlit."""


def build_tree(paths: list[str], strip: str = "") -> dict:
    """{"dir/": {...}, "file.md": "<full path>"} from '/'-separated *paths*, *strip* removed from their front.

    Folder keys end in '/', so a folder and a file of the same name don't collide.
    """
    tree: dict = {}
    for path in paths:
        *dirs, name = path.removeprefix(strip).split("/")
        node = tree
        for d in dirs:
            node = node.setdefault(f"{d}/", {})
        node[name] = path
    return tree


def tree_contains(tree: dict, path: str) -> bool:
    return any(v == path or (isinstance(v, dict) and tree_contains(v, path)) for v in tree.values())
