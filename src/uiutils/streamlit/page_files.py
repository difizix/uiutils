"""Plots, Logs and Arrays pages: pick an output file under a root directory and view it.

*files* is a zero-arg callable returning the current paths (relative to *root*), so the app keeps
its own file list (and its refresh, *on_refresh*) shared with its other pages.
"""

import contextlib
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
import streamlit as st

from uiutils.streamlit.slice_view import render_slices
from uiutils.streamlit.widgets import filtered_select, line_filter
from uiutils.textfilter import filter_lines


def file_meta(path: Path) -> str:
    """`📅 Last Modified: ... | 📦 Size: ... KB` for *path*; raises OSError if it cannot be stat'ed."""
    stats = Path(path).stat()
    mod_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stats.st_mtime))
    return f"📅 Last Modified: {mod_time} | 📦 Size: {stats.st_size / 1024:.2f} KB"


def render_plots(root: Path, get_files: Callable[[], list[str]], on_refresh: Callable[[], None]):
    """Image picker (URL-bound as `?plot=`) and the selected image."""
    col_ctrl, col_view = st.columns([3, 4])
    with col_ctrl:
        files = get_files()
        selected = filtered_select("plot", "Plot", files, on_refresh, icon="🖼️")
    if not selected:
        return
    path = Path(root) / selected
    with col_view:
        st.image(str(path), width="stretch")
        st.write(f"#### `{selected}`")
        with contextlib.suppress(OSError):
            st.caption(file_meta(path))


def render_logs(root: Path, get_files: Callable[[], list[str]], on_refresh: Callable[[], None],
                extra: Callable[[Path], None] | None = None) -> Path | None:
    """Log picker (URL-bound as `?log=`), a line filter and the selected log's text.

    *extra(path)* draws app-specific controls for the selected log, under the picker.
    Returns the selected log's path, None when nothing is selected or it cannot be read.
    """
    col_ctrl, col_view = st.columns([2, 3])
    with col_ctrl:
        files = get_files()
        selected = filtered_select("log", "Log file", files, on_refresh, icon="📄")
        if not selected:
            return None
        path = Path(root) / selected
        if extra:
            extra(path)
        keep, remove = line_filter("log")

    with col_view:
        st.write(f"#### `{selected}`")
        try:
            text, meta = path.read_text(errors="replace"), file_meta(path)
        except OSError as e:
            st.error(f"Failed to read file {selected}: {e}")
            return None
        if keep.strip() or remove.strip():
            lines = filter_lines(text, keep, remove)
            meta += f" | 🔍 Showing {len(lines)} of {len(text.splitlines())} lines"
            text = "\n".join(lines)
        st.caption(meta)
        st.text_area("File Contents", value=text, height=600)
    return path


def render_arrays(root: Path, get_files: Callable[[], list[str]], on_refresh: Callable[[], None]):
    """`.npy`/`.npz` picker (URL-bound as `?arr=`, an npz member as `?arr_key=`) and its slices."""
    col_ctrl, col_meta = st.columns([2, 3])
    with col_ctrl:
        selected = filtered_select("arr", "Array", get_files(), on_refresh, icon="🧊")
    if not selected:
        return
    path = Path(root) / selected
    with col_meta:
        st.write(f"#### `{selected}`")
        try:
            st.caption(file_meta(path))
            if path.suffix != ".npz":
                arr = np.load(path, mmap_mode="r")
            else:
                with np.load(path) as npz:
                    names = npz.files
                    if not names:
                        st.info("Empty npz.")
                        return
                    name = names[0]
                    if len(names) > 1:  # pick which of the npz's arrays to view
                        if st.session_state.get("arr_key") not in names:
                            st.session_state.pop("arr_key", None)
                        name = st.selectbox(f"Member ({len(names)})", names, key="arr_key", bind="query-params")
                    arr = npz[name]
        except (OSError, ValueError) as e:  # unreadable, or pickled object arrays
            st.error(f"Failed to load {selected}: {e}")
            return
    render_slices(arr, "arr_")
