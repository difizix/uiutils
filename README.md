# uiutils

Reusable utilities shared between [porgui] and [difgui] (private atm) and hopefully your (streamlit-based) applications.


> [!CAUTION]
> WIP, unstable

Small GUI helpers, framework-free at the core:

* `uiutils.makefile_targets`: parse a Makefile into targets (with their doc comments and recipes) and `?=` variables.
* `uiutils.argparse_form`: get an `argparse` parser from a script without running it, turn it into form fields, and turn
  form values back into an argv.
* `uiutils.streamlit`: Streamlit widgets built on the above (needs `pip install uiutils[streamlit]`).


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