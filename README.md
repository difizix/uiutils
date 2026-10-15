# uiutils

**uiutils** is a lightweight, modular developer toolkit specifically designed to turn scientific / simulation CLI repositories (with Makefiles, argparse scripts, and markdown docs) into a cohesive Streamlit dashboard without introducing heavy frameworks or altering underlying scripts.

Used in [porgui] and difgui (private) and hopefully your Streamlit-based applications.


> [!NOTE]
> * **Work in Progress**: The API is evolving and subject to change.
> * All forms of collaboration, issues, and feedback are welcome!

Small GUI helpers, framework-free at the core:

* `uiutils.makefile_targets`: parse a Makefile into targets (with their doc comments and recipes) and `?=` variables.
* `uiutils.argparse_form`: get an `argparse` parser from a script without editing it (it runs up to its `parse_args()` call), turn it into form fields, and turn form values back into an argv.
* `uiutils.textfilter`: regex filtering and wrap-around neighbours for list pickers, keep/remove line filtering.
* `uiutils.file_discovery`: plots, logs and markdown reports under a root, newest first, with app rules as `prune`/`keep` callables.
* `uiutils.mdrender`: markdown preprocessing for a viewer: inline images, in-app links, mermaid blocks.
* `uiutils.tree`: a nested folder tree of relative paths, for tree browsers.
* `uiutils.streamlit` (needs the `streamlit` extra): a lazy page factory for `st.navigation`, a filtered picker, argparse forms, a process console, and ready-made Make, Scripts, Plots, Logs, Arrays and Docs pages.
* `uiutils.streamlit.slice_view`: an n-d numpy array slice viewer: normal axis and slice, log scale, colour range relative to min-max, colormaps, axes and colorbar, transpose; used by the Arrays page for `.npy`/`.npz` files.

The core has no dependencies. The `streamlit` extra needs Streamlit >= 1.64 (widgets bound to URL query
parameters); the slice viewer's "Axes & colorbar" option also uses matplotlib, if installed.



## Installation

Not on PyPI yet; install from GitHub:

```bash
pip install "uiutils[streamlit] @ git+https://github.com/difizix/uiutils.git@main"
```

Pin a commit (`@<hash>`) rather than `@main`: the API is still changing.

For development:

```bash
git clone https://github.com/difizix/uiutils.git
cd uiutils
pip install -e ".[streamlit]"
python -m pytest
```

## Quickstart

Save the snippet to a file (e.g., `app.py`); each tool is its own page:

```python
# app.py
from pathlib import Path
import streamlit as st
from uiutils.streamlit.pages import page

root = Path(".")
arrays = [str(p) for p in root.rglob("*.np[yz]")]
st.navigation([
    # Makefile targets with variable overrides and a streaming console
    page("uiutils.streamlit.page_make:render_make", "Make", "🛠️", "make", default=True, args=(root,)),
    # Python scripts with forms generated from their argparse parsers
    page("uiutils.streamlit.page_pyrun:render_pyrun", "Scripts", "🐍", "scripts",
         args=(root, ["scripts/process_data.py"])),
    # .npy/.npz slice viewer
    page("uiutils.streamlit.page_files:render_arrays", "Arrays", "🧊", "arrays",
         args=(root, lambda: arrays, lambda: None)),
]).run()
```

Then launch the Streamlit app, e.g.:

```bash
python -m streamlit run app.py
```


[porgui]: https://github.com/difizix/porgui
