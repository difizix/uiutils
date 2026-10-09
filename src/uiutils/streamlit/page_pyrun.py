"""Scripts page: pick a python script, fill in its argparse options as a form, run it in the console."""

import shlex
import sys
from collections.abc import Callable
from pathlib import Path

import streamlit as st

from uiutils.argparse_form import capture_parser, form2argv, parser2uiparams
from uiutils.streamlit.console import is_proc_running, render_proc_console, start_proc
from uiutils.streamlit.forms import render_parseargs
from uiutils.streamlit.widgets import line_filter


@st.cache_resource(show_spinner="Reading the script's options...")
def _parser(path: str, _mtime: float, sys_paths: tuple[str, ...]):
    """capture_parser, re-run only when the script changes (the mtime is part of the cache key)."""
    for mod_dir in sys_paths:
        if mod_dir not in sys.path:
            sys.path.insert(0, mod_dir)
    return capture_parser(path)


def render_pyrun(root: Path, scripts: list[str], python: str = sys.executable, env: dict[str, str] | None = None,
                 sys_paths: tuple[str, ...] = (), on_done: Callable[[], None] | None = None):
    """Run one of *scripts* (paths relative to *root*) as `python <script> <argv>` in *root*.

    Each script must call ArgumentParser.parse_args() before doing any work: its parser is read
    by running it up to that call (see capture_parser). *sys_paths* are added to this process's
    sys.path for that, for scripts importing project modules; *env* is the subprocess's environment.
    """
    col_ctrl, col_view = st.columns([2, 3])
    with col_ctrl:
        rel_path = st.selectbox("Script", scripts, key="pyrun_script", bind="query-params")
        path = Path(root) / rel_path
        try:
            parser = _parser(str(path), path.stat().st_mtime, tuple(sys_paths))
        except Exception as e:  # noqa: BLE001 -- any import/top-level error of the script itself
            st.error(f"Could not read the options of `{rel_path}`: {e}")
            return
        if parser.description:
            st.caption(parser.description)

        values = render_parseargs(parser2uiparams(parser), key_prefix=f"pyrun_{path.stem}")
        argv = [python, rel_path, *form2argv(parser, values)]
        st.code(shlex.join(argv), language="bash")

        if st.button("▶️ Run", type="primary", disabled=is_proc_running(), key="pyrun_run"):
            start_proc(argv, cwd=root, env=env)

        keep, remove = line_filter("pyrun")

    with col_view:
        render_proc_console(on_done=on_done, height=600, keep=keep, remove=remove)
