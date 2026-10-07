"""Streamlit form for a list of uiutils.argparse_form.FormParam."""

import inspect
from collections.abc import Callable

import streamlit as st

from uiutils.argparse_form import FormParam


def _default_str(default) -> str:
    if default is None or default is inspect.Parameter.empty:
        return ""
    if isinstance(default, (list, tuple)):
        return "\n".join(str(d) for d in default)
    return str(default)


def render_param(param: FormParam, key: str):
    """One widget for *param*, labelled with its name; returns the widget's value.

    Lists are a text area with one value per line; bool, int and float get their own widgets;
    anything else is a text box.
    """
    name, help_text = param.name, param.help_text or None
    if param.is_iterable:
        text = st.text_area(name, value=_default_str(param.default), key=key, help=help_text or "One value per line.")
        return [line.strip() for line in text.splitlines() if line.strip()]
    if param.type_val is bool:
        return st.checkbox(name, value=bool(param.default), key=key, help=help_text)
    if param.type_val in (int, float):
        try:
            value = param.type_val(param.default)
        except (TypeError, ValueError):
            value = param.type_val(0)
        step = 1 if param.type_val is int else 0.1
        return st.number_input(name, value=value, step=step, key=key, help=help_text)
    return st.text_input(name, value=_default_str(param.default), key=key, help=help_text)


def render_parseargs(params: list[FormParam], key_prefix: str = "", num_cols: int = 1,
                     render: Callable[[FormParam, str], object] = render_param) -> dict:
    """Widgets for *params* in *num_cols* columns, as {name: value}.

    *render* draws one param; pass a wrapper around render_param to add app-specific types.
    """
    if not params:
        return {}
    cols = st.columns(num_cols)
    values = {}
    for i, param in enumerate(params):
        with cols[i % num_cols]:
            values[param.name] = render(param, f"{key_prefix}_{param.name}")
    return values
