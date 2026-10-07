"""Plots and Logs pages: pick an output file under a root directory and view it.

*files* is a zero-arg callable returning the current paths (relative to *root*), so the app keeps
its own file list (and its refresh, *on_refresh*) shared with its other pages.
"""

import contextlib
import time
from collections.abc import Callable
from pathlib import Path

import streamlit as st

from uiutils.streamlit.widgets import filtered_select
from uiutils.textfilter import filter_lines


def file_meta(path: Path) -> str:
    """`📅 Last Modified: ... | 📦 Size: ... KB` for *path*; raises OSError if it cannot be stat'ed."""
    stats = Path(path).stat()
    mod_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stats.st_mtime))
    return f"📅 Last Modified: {mod_time} | 📦 Size: {stats.st_size / 1024:.2f} KB"


def render_plots(root: Path, files: Callable[[], list[str]], on_refresh: Callable[[], None]):
    """Image picker (URL-bound as `?plot=`) and the selected image."""
    col_ctrl, col_view = st.columns([3, 4])
    with col_ctrl:
        st.write("### 🖼️ Generated Plots")
        selected = filtered_select("plot", "Select Plot to display:", files(), on_refresh)
    if not selected:
        return
    path = Path(root) / selected
    with col_view:
        st.image(str(path), width="stretch")
        st.write(f"#### `{selected}`")
        with contextlib.suppress(OSError):
            st.caption(file_meta(path))


def _line_filter() -> tuple[str, str]:
    """Keep/remove terms, applied on submit only, so typing does not re-filter a large log."""
    with st.form("log_line_filter", border=False):
        st.write("### 🔍 Filter Log Display")
        keep = st.text_input("Keep lines containing (split by space):", key="log_keep",
                             help="Split by whitespace. If empty, keeps all lines.")
        remove = st.text_input("Remove lines containing (split by space):", key="log_remove",
                               help="Split by whitespace.")
        st.form_submit_button("🚫 Filter", width="stretch")
    return keep, remove


def render_logs(root: Path, files: Callable[[], list[str]], on_refresh: Callable[[], None],
                extra: Callable[[Path], None] | None = None):
    """Log picker (URL-bound as `?log=`), a line filter and the selected log's text.

    *extra(path)* draws app-specific controls for the selected log, under the picker.
    """
    col_ctrl, col_view = st.columns([2, 3])
    with col_ctrl:
        st.write("### 📄 Output Log Files")
        selected = filtered_select("log", "Select Log file to display:", files(), on_refresh)
        if not selected:
            return
        path = Path(root) / selected
        if extra:
            extra(path)
        keep, remove = _line_filter()

    with col_view:
        st.write(f"#### `{selected}`")
        try:
            text, meta = path.read_text(errors="replace"), file_meta(path)
        except OSError as e:
            st.error(f"Failed to read file {selected}: {e}")
            return
        if keep.strip() or remove.strip():
            lines = filter_lines(text, keep, remove)
            meta += f" | 🔍 Showing {len(lines)} of {len(text.splitlines())} lines"
            text = "\n".join(lines)
        st.caption(meta)
        st.text_area("File Contents", value=text, height=600)
