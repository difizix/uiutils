"""Make page: pick a target of a Makefile, override its `?=` variables, run it in the console."""

from collections.abc import Callable
from pathlib import Path

import streamlit as st

from uiutils.makefile_targets import parse_makefile
from uiutils.streamlit.console import is_proc_running, render_proc_console, start_proc
from uiutils.streamlit.widgets import filtered_select


def render_make(root: Path, on_done: Callable[[], None] | None = None):
    """Targets of `<root>/Makefile`, run with `make` in *root*; *on_done* runs when make exits."""
    st.write("### 🛠️ Make targets")
    makefile = Path(root) / "Makefile"
    if not makefile.is_file():
        st.info(f"No Makefile in {root}.")
        return

    targets, variables = parse_makefile(makefile)
    by_name = {t.name: t for t in targets}
    name = filtered_select("mk", "Target", list(by_name), on_refresh=lambda: None)
    if name is None:
        return
    target = by_name[name]
    if target.doc:
        st.caption(target.doc)
    st.code("\n".join(target.recipe) or "(no recipe)", language="makefile")

    overrides = []
    if variables:
        with st.expander("Variables (`?=` defaults)", expanded=False):
            cols = st.columns(2)
            for i, (var, default) in enumerate(variables.items()):
                val = cols[i % 2].text_input(var, value=default, key=f"mk_var_{var}")
                if val != default:
                    overrides.append(f"{var}={val}")

    argv = ["make", name, *overrides]
    st.code(" ".join(argv), language="bash")
    if st.button("▶️ Run", type="primary", disabled=is_proc_running(), key="mk_run"):
        start_proc(argv, cwd=root)

    render_proc_console(on_done=on_done)
