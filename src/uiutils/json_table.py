"""Nested JSON as a long table: one row per numeric leaf, its key path as label columns.

No streamlit or pandas here, so it can be tested and reused without a GUI.
"""


def json_long(obj) -> list[dict]:
    """One row per numeric leaf: `level0, level1, ...` hold its key path (fewer for a shallower
    leaf), `value` the number. Lists and non-numeric leaves are left out."""
    rows = []

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, (*path, str(k)))
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            rows.append({**{f"level{i}": k for i, k in enumerate(path)}, "value": node})

    walk(obj, ())
    return rows
