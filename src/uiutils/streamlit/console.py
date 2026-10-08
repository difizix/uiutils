"""One background process per session, with its output streamed into a console.

State lives in st.session_state (`running_process`, `output_queue`, `process_log`, `last_status`),
so every page that calls start_proc shares the same slot: one process at a time per session.
"""

import contextlib
import os
import queue
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

import streamlit as st


def _pump(proc: subprocess.Popen, out_q: queue.Queue) -> None:
    assert proc.stdout, "proc.stdout is not captured"
    for line in iter(proc.stdout.readline, ""):
        out_q.put(line)
    proc.stdout.close()
    proc.wait()
    out_q.put(None)  # EOF


def is_proc_running() -> bool:
    return st.session_state.get("running_process") is not None


def start_proc(argv: list[str], cwd: Path | str, env: dict[str, str] | None = None) -> None:
    """Start *argv* in its own process group and rerun, so render_proc_console streams it."""
    ss = st.session_state
    ss.process_log = []
    try:
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(cwd), env=env,
                                text=True, bufsize=1, start_new_session=True)
    except OSError as e:
        ss.last_status = "Failed to start"
        st.error(f"Failed to start `{argv[0]}`: {e}")
        return
    out_q = queue.Queue()
    threading.Thread(target=_pump, args=(proc, out_q), daemon=True).start()
    ss.running_process, ss.output_queue = proc, out_q
    ss.last_status = "Running"
    st.rerun()


def _drain() -> int | None:
    """Move queued output into process_log; return the exit code once the process has ended."""
    ss = st.session_state
    while True:
        try:
            line = ss.output_queue.get_nowait()
        except queue.Empty:
            return None
        if line is None:
            return ss.running_process.wait()
        ss.process_log.append(line)


def _stop() -> None:
    """Terminate the whole process group: `make`/`inv` children too, not only the parent."""
    ss = st.session_state
    with contextlib.suppress(ProcessLookupError):  # already exited
        os.killpg(ss.running_process.pid, signal.SIGTERM)
    ss.running_process = ss.output_queue = None
    ss.last_status = "Terminated"


def render_proc_console(on_done: Callable[[], None] | None = None, height: int = 350) -> None:
    """Stop/Clear buttons and the output of the session's process, polled while it runs.

    Call it last on the page: while the process runs, it reruns the script every 50 ms.
    """
    ss = st.session_state
    exit_code = _drain() if ss.get("running_process") is not None else None
    if exit_code is not None:
        ss.running_process = ss.output_queue = None
        ss.last_status = "Success" if exit_code == 0 else f"Failed (code {exit_code})"
        if on_done:
            on_done()

    running = is_proc_running()
    stop_col, clear_col, status_col = st.columns([1, 1, 4])
    stop_col.button("⏹️ Stop", disabled=not running, on_click=_stop, key="console_stop")
    if clear_col.button("🧹 Clear", disabled=running, key="console_clear"):
        ss.process_log = []
    status_col.caption(f"Status: {ss.get('last_status', 'Idle')}")

    if ss.get("process_log"):
        with st.container(height=height):
            st.code("".join(ss.process_log), language="text")

    if running:
        time.sleep(0.05)
        st.rerun()
