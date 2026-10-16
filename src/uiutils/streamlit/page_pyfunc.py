"""Arrays page: pick a function, fill in its arguments, view each array it returns in its own row.

*funcs* maps a label to a function: a `"module:func"` string (imported when picked), a callable, or
a `(function, uiparams)` pair whose *uiparams(func)* replaces the page's for that function.
The function returns an array, a tuple/list of arrays or a {label: array} dict. Row 1 holds the
function, its arguments and the first array's slice controls, next to that array; each further
array gets a row of its own, its widgets URL-bound under its own prefix (`arr_`, `arr1_`, ...).
"""

import inspect
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import numpy as np
import streamlit as st

from uiutils.argparse_form import FormParam
from uiutils.func_form import form2kwargs, func2uiparams, import_target
from uiutils.streamlit.forms import render_param, render_parseargs
from uiutils.streamlit.page_files import file_meta
from uiutils.streamlit.slice_view import render_slices
from uiutils.streamlit.widgets import filtered_select


def read_array(path: Annotated[str, "array_file"]):
    """The array in a `.npy` file, or a `.npz` file's arrays as {member: array}."""
    if Path(path).suffix != ".npz":
        return np.load(path, mmap_mode="r")
    with np.load(path) as npz:
        return {name: npz[name] for name in npz.files}


def array_file_param(root: Path, get_files: Callable[[], list[str]], on_refresh: Callable[[], None]):
    """A *render* for render_pyfunc: an `"array_file"` param is a picker (URL-bound as `?arr=`) over
    *get_files()* (paths relative to *root*), the rest go to render_param. Its Refresh also forgets the
    last output, so a rewritten file is read again."""
    def refresh():
        st.session_state.pop("pyfunc_out", None)
        on_refresh()

    def render(param: FormParam, key: str, bind: str | None = None):
        if param.type_val != "array_file":
            return render_param(param, key, bind=bind)
        selected = filtered_select("arr", "Array", get_files(), refresh, icon="🧊")
        if not selected:
            st.stop()
        path = Path(root) / selected
        try:
            st.caption(file_meta(path))
        except OSError as e:
            st.error(f"Cannot read `{selected}`: {e}")
            st.stop()
        return str(path)

    return render


def _named(out) -> list[tuple[str, object]]:
    if isinstance(out, dict):
        return list(out.items())
    if isinstance(out, (tuple, list)):
        return [(f"output {i}", a) for i, a in enumerate(out)]
    return [("output", out)]


def _outputs(label: str, func, kwargs: dict, rerun: bool):
    """func(**kwargs) as [(name, array)], kept from the last rerun unless the function, its arguments
    or *rerun* say otherwise; so view widgets do not re-run it, nor redraw a random field."""
    key = (label, repr(kwargs))
    cached = st.session_state.get("pyfunc_out")
    if rerun or not cached or cached[0] != key:
        st.session_state.pyfunc_out = (key, _named(func(**kwargs)))
    return st.session_state.pyfunc_out[1]


def render_pyfunc(funcs: dict[str, object], uiparams: Callable[..., list[FormParam]] = func2uiparams,
                  render: Callable[..., object] = render_param):
    """Function picker (URL-bound as `?pyfunc=`), its arguments and a slice view per returned array.

    *uiparams(func)* gives a function's form params; *render* draws one (see render_parseargs).
    """
    col_ctrl, col_view = st.columns([2, 3])
    with col_ctrl:
        label = st.selectbox("Function", list(funcs), key="pyfunc", bind="query-params")
        target, get_params = funcs[label] if isinstance(funcs[label], tuple) else (funcs[label], uiparams)
        try:
            func = import_target(target) if isinstance(target, str) else target
            params = get_params(func)
        except Exception as e:  # a broken registry entry is shown, not a crash
            st.error(f"Cannot load `{label}`: {e}")
            return
        doc = inspect.getdoc(func)
        if doc:
            st.caption(doc.split("\n\n")[0])
        values = render_parseargs(params, key_prefix=f"pyfunc_{label}", render=render)
        rerun = st.button("🎲 Rerun", key="pyfunc_rerun", help="Run again with the same arguments, e.g. for a new random draw.")
        try:
            outs = _outputs(label, func, form2kwargs(params, values), rerun)
        except Exception as e:  # bad arguments or a failing function: show why
            st.error(f"`{label}` failed: {type(e).__name__}: {e}")
            return

    for i, (name, arr) in enumerate(outs):
        if i == 0:
            col_ctrl.write(f"#### `{name}`")
            cols = (col_ctrl, col_view)
        else:
            st.divider()
            st.write(f"#### `{name}`")
            cols = None
        render_slices(arr, "arr_" if i == 0 else f"arr{i}_", info=f"`{name}`", cols=cols)
