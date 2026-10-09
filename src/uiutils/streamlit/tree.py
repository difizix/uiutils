"""Collapsible tree of `st.page_link`s: a folder is an expander, a file a link to `page?<param>=<path>`.

A page_link with query params pushes a browser history entry, so back/forward walk through the
visited files (a URL-bound widget only replaces the URL).
"""

import streamlit as st

from uiutils.tree import tree_contains


def render_tree(tree: dict, page: st.Page, param: str, selected: str | None, expand_all: bool = False):
    """Folders first, then files, each alphabetically; folders holding *selected* start expanded."""
    for name in sorted(tree, key=lambda n: (not n.endswith("/"), n.lower())):
        node = tree[name]
        if isinstance(node, dict):
            open_ = expand_all or (selected is not None and tree_contains(node, selected))
            with st.expander(f"📁 {name.rstrip('/')}", expanded=open_):
                render_tree(node, page, param, selected, expand_all)
        else:
            st.page_link(page, label=f"**{name}**" if node == selected else name,
                         icon="👉" if node == selected else "📄", query_params={param: node})
