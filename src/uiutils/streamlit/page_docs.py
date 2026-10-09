"""Docs page and markdown renderer: inlined images, page-link buttons, mermaid diagrams.

*pages* maps a url_path to its `st.Page` (needed by `st.page_link`); *root* is the repo root that
`docs?doc=` labels and relative links are resolved against.
"""

from pathlib import Path
from urllib.parse import parse_qsl

import streamlit as st
import streamlit.components.v1 as components

from uiutils.file_discovery import find_reports
from uiutils.mdrender import (
    resolve_markdown_images,
    resolve_markdown_links,
    split_mermaid_blocks,
    split_trailing_links,
)
from uiutils.streamlit.page_files import file_meta
from uiutils.streamlit.widgets import filtered_select

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


def _render_prose(lines: list[str], md_dir: Path, root: Path):
    if lines:
        st.markdown(resolve_markdown_links("\n".join(lines), md_dir, root), unsafe_allow_html=True)


def _render_with_page_links(md: str, md_dir: Path, root: Path, pages: dict):
    """Markdown whose list items' trailing GUI links (see `split_trailing_links`) are rendered as
    `st.page_link` buttons, which switch page in place. Other links become same-tab `<a>` tags,
    which reload the app."""
    prose: list[str] = []
    in_fence = False
    for line in md.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        text, links = (line, []) if in_fence else split_trailing_links(line, md_dir, root)
        if not links:
            prose.append(line)
            continue
        _render_prose(prose, md_dir, root)
        prose = []
        if text.strip(" -*+"):
            _render_prose([text.lstrip()], md_dir, root)  # lstrip: an indented line alone is a code block
        with st.container(horizontal=True):
            for label, route in links:
                page, _, query = route.partition("?")
                if page in pages:
                    st.page_link(pages[page], label=label, query_params=dict(parse_qsl(query)))
                else:
                    st.markdown(f"[{label}]({route})")
    _render_prose(prose, md_dir, root)


def render_markdown(md: str, md_dir: Path, root: Path, pages: dict):
    """Render a markdown doc, *md_dir* being the directory its relative links start from."""
    md = resolve_markdown_images(md, md_dir)
    for kind, val in split_mermaid_blocks(md):
        if kind == "markdown":
            _render_with_page_links(val, md_dir, root, pages)
        elif kind == "mermaid":
            _render_mermaid(val)


def render_docs(root: Path, pages: dict):
    """Markdown picker (URL-bound as `?doc=`) and the selected document."""
    sstate = st.session_state

    def refresh():
        sstate.report_files = find_reports(root)

    if "report_files" not in sstate:
        refresh()
    col_ctrl, col_view = st.columns([1, 3])
    with col_ctrl:
        selected = filtered_select("doc", "Select Document:", sstate.report_files, refresh, icon="📋")
    if not selected:
        return
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
