"""Docs page (tree browser + viewer) and markdown renderer: inlined images, page-link buttons, mermaid diagrams.

*pages* maps a url_path to its `st.Page` (needed by `st.page_link`); *root* is the repo root that
`docs?doc=` labels and relative links are resolved against.
"""

from collections.abc import Sequence
from pathlib import Path
from urllib.parse import parse_qsl

import streamlit as st
import streamlit.components.v1 as components

from uiutils.file_discovery import find_reports
from uiutils.mdrender import (
    is_table_separator,
    resolve_markdown_images,
    resolve_markdown_links,
    split_cell_links,
    split_mermaid_blocks,
    split_table_row,
    split_trailing_links,
)
from uiutils.streamlit.page_files import file_meta
from uiutils.streamlit.tree import render_tree
from uiutils.textfilter import filter_by_search_query
from uiutils.tree import build_tree

_NUM_RECENT = 30

_MERMAID_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ background-color: transparent; margin: 0; padding: 10px; overflow: auto;
               display: flex; justify-content: center; align-items: center; }}
        .mermaid {{ margin: 0 auto; text-align: center; }}
    </style>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{
            startOnLoad: true, theme: 'dark', securityLevel: 'loose',
            themeVariables: {{ background: '#0d0d1e', primaryColor: '#1f1f38', primaryTextColor: '#e6e6ea',
                              lineColor: '#00ffcc', textColor: '#e6e6ea' }}
        }});
    </script>
</head>
<body><pre class="mermaid">
{code}
</pre></body>
</html>"""


def _render_mermaid(code: str):
    height = max(180, min(1000, len(code.split("\n")) * 38 + 60))  # heuristic from the line count
    components.html(_MERMAID_HTML.format(code=code), height=height, scrolling=True)


def _render_prose(lines: list[str], md_dir: Path, root: Path, width="auto"):
    if lines:
        st.markdown(resolve_markdown_links("\n".join(lines), md_dir, root), unsafe_allow_html=True, width=width)


def _page_link(label: str, route: str, pages: dict):
    page, _, query = route.partition("?")
    if page in pages:
        st.page_link(pages[page], label=label, query_params=dict(parse_qsl(query)))
    else:
        st.markdown(f"[{label}]({route})")


def _render_table_grid(rows: list[list[list[tuple[str, str | None]]]], md_dir: Path, root: Path, pages: dict):
    """A table (header row first, cells as `split_cell_links` segments) as a grid of columns, so that
    its in-app links can be `st.page_link` buttons, which a markdown table cannot hold."""
    ncols = max(len(r) for r in rows)
    weights = [min(40, max(3, *(sum(len(s) for s, _ in r[j]) for r in rows if j < len(r)))) for j in range(ncols)]
    with st.container(border=True, gap="small"):
        for i, row in enumerate(rows):
            for col, segments in zip(st.columns(weights, gap="small", vertical_alignment="center"), row, strict=False):
                with col, st.container(horizontal=True, vertical_alignment="center", gap="small"):
                    for text, route in segments:
                        if route is not None:
                            _page_link(text, route, pages)
                        elif text:
                            _render_prose([f"**{text}**" if i == 0 else text], md_dir, root, width="content")


def _render_with_page_links(md: str, md_dir: Path, root: Path, pages: dict):
    """Markdown whose list items' trailing GUI links (see `split_trailing_links`) are rendered as
    `st.page_link` buttons in one row after the item text (content-sized), which switch page in place.
    Tables holding a GUI link are drawn as a grid of columns with such buttons in the cells. Other links
    become same-tab `<a>` tags, which reload the app."""
    prose: list[str] = []
    in_fence = False
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not in_fence and line.lstrip().startswith("|") and i < len(lines) and is_table_separator(lines[i]):
            end = i + 1
            while end < len(lines) and lines[end].lstrip().startswith("|"):
                end += 1
            block = [line, *lines[i + 1:end]]
            rows = [[split_cell_links(c, md_dir, root) for c in split_table_row(r)] for r in block]
            if any(route for r in rows for c in r for _, route in c):
                _render_prose(prose, md_dir, root)
                prose = []
                _render_table_grid(rows, md_dir, root, pages)
            else:
                prose += lines[i - 1:end]
            i = end
            continue
        text, links = (line, []) if in_fence else split_trailing_links(line, md_dir, root)
        if not links:
            prose.append(line)
            continue
        _render_prose(prose, md_dir, root)
        prose = []
        with st.container(horizontal=True, vertical_alignment="center"):
            if text.strip(" -*+"):
                _render_prose([text.lstrip()], md_dir, root, width="content")  # lstrip: an indented line alone is a code block
            for label, route in links:
                _page_link(label, route, pages)
    _render_prose(prose, md_dir, root)


def render_markdown(md: str, md_dir: Path, root: Path, pages: dict):
    """Render a markdown doc, *md_dir* being the directory its relative links start from."""
    md = resolve_markdown_images(md, md_dir)
    for kind, val in split_mermaid_blocks(md):
        if kind == "markdown":
            _render_with_page_links(val, md_dir, root, pages)
        elif kind == "mermaid":
            _render_mermaid(val)


def _open_recent():
    st.query_params["doc"] = st.session_state.docrecent
    st.session_state.docrecent = None


def render_docs(root: Path, pages: dict, subdir: str | Sequence[str], default: str):
    """Tree of the markdown files under *root*/*subdir* and the selected one (`?doc=`, *default* if unset).

    *subdir* may be several folders under *root*, e.g. `("docs", "runs")`; each is then a top-level
    folder of the tree. Served by `pages["docs"]`, the route `gui_href` maps relative `.md` links to.
    """
    sstate = st.session_state
    subdirs = [subdir] if isinstance(subdir, str) else list(subdir)
    if "report_files" not in sstate:
        sstate.report_files = [f"{d}/{f}" for d in subdirs for f in find_reports(Path(root) / d)]
    selected = st.query_params.get("doc", default)
    st.query_params["doc"] = selected  # keep the URL in step with the shown doc (Home is the default page)

    col_ctrl, col_view = st.columns([1, 3])
    with col_ctrl:
        with st.container(horizontal=True, vertical_alignment="bottom"):
            query = st.text_input("Filter (regex)",
                placeholder="Filter (regex) names...",
                label_visibility="collapsed",
                key="docq", bind="query-params")
            if st.button("🔄", help="Rescan the markdown files"):
                del sstate.report_files
                st.rerun()
            # report_files is newest first; on_change (not a post-check) so a later tree click isn't overridden
        st.selectbox("📒", sstate.report_files[:_NUM_RECENT], index=None, placeholder="📒 Recent edits", key="docrecent",
                        label_visibility="collapsed", help="Most recently modified docs, newest first",
                        on_change=_open_recent)
        files, bad_regex = filter_by_search_query(sstate.report_files, query)
        if bad_regex:
            st.error("Invalid regex")
        render_tree(build_tree(files, strip=f"{subdirs[0]}/" if len(subdirs) == 1 else ""), pages["docs"], "doc", selected, expand_all=bool(query.strip()))

    path = Path(root) / selected
    with col_view:
        st.write(f"#### `{selected}`")
        try:
            st.caption(file_meta(path))
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            st.error(f"Error reading file `{selected}`: {e}")
            return
        render_markdown(content, path.parent, root, pages)
