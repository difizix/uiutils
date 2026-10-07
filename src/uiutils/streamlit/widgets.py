"""Streamlit widgets over uiutils.textfilter."""

import streamlit as st

from uiutils.textfilter import cycle_neighbors, filter_by_search_query


def filtered_select(name, label, items, on_refresh):
    """Refresh button, regex filter box, selectbox and Previous/Next buttons over *items*.

    The selection and the filter text are bound to the URL as `?<name>=...&<name>q=...`, so
    *name* must be unique across pages. Returns the selected item, or None when the filter matches
    nothing.
    """
    ref_col, search_col = st.columns([1, 2])
    ref_col.button("🔄 Refresh", key=f"{name}_refresh", on_click=on_refresh)
    query = search_col.text_input(f"Filter {label}", placeholder="Search/filter (regex)...",
                                  label_visibility="collapsed", key=f"{name}q", bind="query-params")

    filtered, has_err = filter_by_search_query(items, query)
    if has_err:
        st.caption("⚠️ *Invalid regex pattern*")
    elif query.strip():
        st.caption(f"🔍 Filtering by `{query}` ({len(filtered)} of {len(items)})")
    if not filtered:
        st.info("No matches.")
        return None

    selected = st.selectbox(label, filtered, format_func=str, key=name, bind="query-params")

    def select(item):
        st.session_state[name] = item

    prev_item, next_item = cycle_neighbors(filtered, selected)
    prev_col, next_col = st.columns(2)
    prev_col.button("⬅️ Previous", key=f"{name}_prev", width="stretch", on_click=select, args=(prev_item,))
    next_col.button("➡️ Next", key=f"{name}_next", width="stretch", on_click=select, args=(next_item,))
    return selected
