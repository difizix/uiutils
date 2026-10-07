"""st.Page factory for st.navigation, importing a page's module only when the page is opened."""

import importlib

import streamlit as st


def page(target: str, title: str, icon: str, url_path: str, default: bool = False, args: tuple = ()) -> st.Page:
    """Page served at /<url_path> that runs `module:func(*args)`.

    st.page_link matches a page by url_path alone, so a second page() call with the same
    url_path can be used to link to it.
    """
    module, func = target.split(":")

    def run():
        getattr(importlib.import_module(module), func)(*args)

    return st.Page(run, title=title, icon=icon, url_path=url_path, default=default)
