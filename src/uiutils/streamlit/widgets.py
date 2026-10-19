"""Streamlit widgets over uiutils.textfilter."""

import contextlib
import re
from pathlib import Path

import streamlit as st

from uiutils.textfilter import cycle_neighbors, filter_by_search_query


def filtered_select(name, label, items, on_refresh, icon=""):
    """Refresh button, regex filter box, selectbox and Previous/Next buttons over *items*.

    The selection and the filter text are bound to the URL as `?<name>=...&<name>q=...`, so
    *name* must be unique across pages. Returns the selected item, or None when the filter matches
    nothing.
    """
    ref_col, search_col = st.columns([1, 2])
    ref_col.button("🔄 Refresh", key=f"{name}_refresh", on_click=on_refresh)
    query = search_col.text_input(f"_Filter {label}", placeholder=f"{label} search/filter (regex)..., {len(items)} in total",
                                  label_visibility="collapsed", key=f"{name}q", bind="query-params")

    filtered, has_err = filter_by_search_query(items, query)
    if has_err:
        st.caption("⚠️ *Invalid regex pattern*")
    elif query.strip():
        st.caption(f"🔍 Filtering by `{query}` ({len(filtered)} of {len(items)})")
    if not filtered:
        st.info("No matches.")
        return None

    selected = st.selectbox(f"{icon} Select {label}", filtered, format_func=str, key=name, accept_new_options=True, bind="query-params")

    def select(item):
        st.session_state[name] = item

    prev_item, next_item = cycle_neighbors(filtered, selected)
    prev_col, next_col = st.columns(2)
    prev_col.button("⬅️ Previous", key=f"{name}_prev", width="stretch", on_click=select, args=(prev_item,))
    next_col.button("➡️ Next", key=f"{name}_next", width="stretch", on_click=select, args=(next_item,))
    return selected


def line_filter(key_prefix: str = "log") -> tuple[str, str]:
    """Keep/remove terms, applied on submit only, so typing does not re-filter a large log.

    URL-bound as `?<key_prefix>_keep=` and `?<key_prefix>_remove=`; collapsed unless one is set."""
    keys = (f"{key_prefix}_keep", f"{key_prefix}_remove")
    active = any(st.session_state.get(k) or st.query_params.get(k) for k in keys)
    with st.expander("🔍 Filter log lines", expanded=active), st.form(f"{key_prefix}_line_filter", border=False):
        keep = st.text_input("Keep lines containing (split by space):", key=f"{key_prefix}_keep", bind="query-params",
                             help="Split by whitespace. Words or regex. If empty, keeps all lines.")
        remove = st.text_input("Remove lines containing (split by space):", key=f"{key_prefix}_remove", bind="query-params",
                               help="Split by whitespace. Words or regex.")
        st.form_submit_button("🚫 Filter", width="stretch")
    return keep, remove


_PNG_RE = re.compile(r"[\w./-]+\.png\b")
_LOGTO_RE = re.compile(r"Logging to: (\S+)")  # difiz utils_sh.logto: the rest of the output is in that file
_ENTER_RE = re.compile(r"Entering directory '([^']+)'")  # difiz utils_sh.runin: the cwd of what follows


def _text_pngs(text: str, bases: list[Path]) -> list[Path]:
    """Existing .png files *text* mentions (e.g. `Wrote sim_data/x/qhist_plot.png`), in order of first
    mention, also in the logs it hands over to (`Logging to: <file>`, one level). A relative path resolves
    against the first of *bases*, then of the `Entering directory '<dir>'` folders in the text, holding it."""
    for sub in _LOGTO_RE.findall(text):
        with contextlib.suppress(OSError):
            text += Path(sub).read_text(errors="replace")
    bases = [*bases, *map(Path, _ENTER_RE.findall(text))]
    found = {}
    for m in _PNG_RE.findall(text):
        hit = next((b / m for b in bases if (b / m).is_file()), None)
        if hit:
            found.setdefault(hit.resolve(), None)
    return list(found)


def png_grid(text: str, root: Path, key: str, bases: tuple[Path, ...] = (), n_cols: int = 3, max_shown: int = 30):
    """The plots a log's *text* mentions, as an image grid filterable by a regex on their paths, captioned
    relative to *root*. Relative paths resolve against *bases*, then *root* (see _text_pngs)."""
    root = Path(root).resolve()
    pngs = [str(p.relative_to(root)) if p.is_relative_to(root) else str(p)
            for p in _text_pngs(text, [*bases, root])]
    if not pngs:
        return
    hdr_col, filt_col = st.columns([2, 3])
    hdr_col.markdown(f"### 🖼️ Plots in this log ({len(pngs)})")
    query = filt_col.text_input("Filter plots:", placeholder="regex on the path, e.g. synthgeo17|perm_",
                                label_visibility="collapsed", key=f"{key}_png_filter")
    if query.strip():
        pngs, has_err = filter_by_search_query(pngs, query)
        if has_err:
            st.caption("⚠️ *Invalid regex pattern*")
    if len(pngs) > max_shown:
        st.caption(f"Showing the first {max_shown} of {len(pngs)}; filter to see others.")
    cols = st.columns(n_cols)
    for i, rel in enumerate(pngs[:max_shown]):
        with cols[i % n_cols]:
            st.image(str(root / rel), caption=rel, width="stretch")


def log_png_grid(log: Path, root: Path, key: str, n_cols: int = 3):
    """png_grid of a log file; its relative paths resolve against the log's folder or the first parent,
    up to *root*, holding them: a run's working dir, e.g. runs/<stage>/."""
    log, root = Path(log).resolve(), Path(root).resolve()
    with contextlib.suppress(OSError):
        bases = tuple(d for d in (log.parent, *log.parents) if d.is_relative_to(root))
        png_grid(log.read_text(errors="replace"), root, key, bases=bases, n_cols=n_cols)
