"""Studio page: pick a file under a root by glob, view and edit it; the caller injects the actions.

The page itself never writes an existing file: saving, running etc. are buttons the caller draws via
*toolbar(path, text)* (e.g. `save_button`), so an inspection-only page cannot modify files by accident.
"""

from collections.abc import Callable
from fnmatch import fnmatch
from pathlib import Path

import streamlit as st

LANGS = {".py": "python", ".json": "json", ".md": "markdown", ".sh": "sh"}


def _editor(path: Path, text: str, key: str) -> str:
    """The edited text; `streamlit-code-editor` if installed, else a text area."""
    try:
        from code_editor import code_editor  # noqa: PLC0415 -- optional dependency
    except ImportError:
        return st.text_area(path.name, value=text, height=600, key=key, label_visibility="collapsed")
    resp = code_editor(text, lang=LANGS.get(path.suffix, "text"), theme="monokai", key=key,
                       options={"wrap": True}, response_mode=["debounce", "blur"])
    return resp.get("text") or text  # "" until the editor's first event


def render_studio(root: Path, globs: tuple[str, ...], toolbar: Callable[[Path | None, str], None] | None = None,
                  template: str = "", key: str = "studio") -> tuple[Path | None, str]:
    """Pick a file under *root* matching one of *globs* (relative to *root*), edit it; returns (path, edited text).

    A typed name matching *globs* that does not exist yet can be created from *template*.
    *toolbar(path, text)* is drawn next to the file selector. The selection is bound to the URL as
    `?<key>_file=...`, so *key* must be unique across pages.
    """
    files = sorted({str(p.relative_to(root)) for g in globs for p in root.glob(g) if p.is_file()})
    sel_col, tool_col = st.columns([2, 3])
    rel = sel_col.selectbox("File", files, index=0 if files else None, key=f"{key}_file", accept_new_options=True,
                            placeholder=" | ".join(globs), label_visibility="collapsed", bind="query-params")
    path, text = None, ""
    if rel:
        path = (root / rel).resolve()
        if not path.exists():
            if not any(fnmatch(rel, g) for g in globs) or not path.is_relative_to(root.resolve()):
                st.error(f"`{rel}` does not match {', '.join(f'`{g}`' for g in globs)}.")
                path = None
            elif st.button(f"🆕 Create `{rel}`", key=f"{key}_create"):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(template)
                st.rerun()
            else:
                path = None
    if path:
        text = _editor(path, path.read_text(), key=f"{key}_text_{rel}")
    elif not files:
        st.info(f"No files match {', '.join(f'`{g}`' for g in globs)}; type a name to create one.")
    if toolbar:
        with tool_col:
            toolbar(path, text)
    return path, text


def save_button(path: Path | None, text: str, key: str = "studio_save") -> None:
    """💾 Save: writes *text* to *path*; disabled while they agree. For toolbars of render_studio."""
    changed = path is not None and text != path.read_text()
    if st.button("💾 Save", key=key, disabled=not changed, type="primary" if changed else "secondary"):
        path.write_text(text)
        st.toast(f"Saved {path.name}", icon="💾")
        st.rerun()
