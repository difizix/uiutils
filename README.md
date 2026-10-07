# uiutils

**uiutils** is a lightweight, modular developer toolkit specifically designed to turn scientific / simulation CLI repositories (with Makefiles, argparse scripts, and markdown docs) into a cohesive Streamlit dashboard without introducing heavy frameworks or altering underlying scripts.

Used in [porgui] and [difgui] (private atm) and hopefully your Streamlit-based applications.


> [!NOTE]
> * **Work in Progress**: The API is evolving and subject to change.
> * All forms of collaboration, issues, and feedback are welcome!

Small GUI helpers, framework-free at the core:

* `uiutils.makefile_targets`: parse a Makefile into targets (with their doc comments and recipes) and `?=` variables.
* `uiutils.argparse_form`: get an `argparse` parser from a script without editing it (it runs up to its `parse_args()` call), turn it into form fields, and turn form values back into an argv.
* `uiutils.textfilter`: regex filtering and wrap-around neighbours for list pickers, keep/remove line filtering.
* `uiutils.mdrender`: markdown preprocessing for a viewer: inline images, in-app links, mermaid blocks.
* `uiutils.streamlit` (needs `pip install uiutils[streamlit]`): a lazy page factory for `st.navigation`, a filtered picker, argparse forms, a process console, and ready-made Make, Scripts, Plots and Logs pages.

The core has no dependencies; `streamlit` is the only optional one.


## Quickstart

Save the snippet to a file (e.g., `app.py`):

```python
# app.py
from pathlib import Path
import streamlit as st
from uiutils.streamlit.page_make import render_make
from uiutils.streamlit.page_pyrun import render_pyrun

st.title("Project Dashboard")

# 1. Interactive Makefile runner with variable overrides & streaming console
render_make(root=Path("."))

# 2. Interactive Python script runner with auto-generated argparse forms
render_pyrun(root=Path("."), scripts=["scripts/process_data.py"])
```

Then launch the Streamlit app, e.g.:

```bash
python -m streamlit run app.py
```


## Installation

From PyPI:

```bash
pip install uiutils[streamlit]
```

Or directly from GitHub:

```bash
pip install "uiutils[streamlit] @ git+https://github.com/difizix/uiutils.git"
```

For development:

```bash
git clone https://github.com/difizix/uiutils.git
cd uiutils
pip install -e ".[streamlit]"
python -m pytest
```


[porgui]: https://github.com/difizix/porgui
[difgui]: https://github.com/difizix/difiz
