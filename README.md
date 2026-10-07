# uiutils

Reusable utilities shared between [porgui] and [difgui] (private atm) and hopefully your (streamlit-based) applications.


> [!CAUTION]
> WIP, unstable

Small GUI helpers, framework-free at the core:

* `uiutils.makefile_targets`: parse a Makefile into targets (with their doc comments and recipes) and `?=` variables.
* `uiutils.argparse_form`: get an `argparse` parser from a script without running it, turn it into form fields, and turn
  form values back into an argv.
* `uiutils.textfilter`: regex filtering and wrap-around neighbours for list pickers.
* `uiutils.mdrender`: markdown preprocessing for a viewer: inline images, in-app links, mermaid blocks.
* `uiutils.streamlit` (needs `pip install uiutils[streamlit]`): a lazy page factory for `st.navigation`, a filtered
  picker, argparse forms, a process console, and ready-made Make and Scripts pages.

The core has no dependencies; `streamlit` is the only optional one.


Installing from pypi

```bash
pip install uiutils[streamlit]
```

Installing for development

```bash
pip install -e ".[streamlit]"
python -m pytest
```


[porgui]: https://github.com/difizix/porgui
[difgui]: https://github.com/difizix/difiz