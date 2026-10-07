"""argparse parser <-> form fields <-> argv, without a GUI framework.

`capture_parser` gets a script's parser, `parser2uiparams` turns it into FormParams for a form
renderer, and `form2argv` turns the form's values back into the script's command line.
"""

import argparse
import runpy
import sys
from pathlib import Path


class FormParam:
    def __init__(self, name, default, has_default, type_val, help_text="", is_iterable=False):
        self.name = name
        self.default = default
        self.has_default = has_default
        self.type_val = type_val
        self.help_text = help_text
        self.is_iterable = is_iterable


def parser2uiparams(parser: argparse.ArgumentParser, fixedargs=None) -> list[FormParam]:
    """One FormParam per argument of *parser*, except --help and the dests in *fixedargs*."""
    fixedargs = fixedargs or {}
    ui_params = []
    for action in parser._actions:
        if isinstance(action, argparse._HelpAction) or action.dest in fixedargs:
            continue
        default = action.default
        is_iterable = action.nargs in ("+", "*")
        if is_iterable:
            type_val = list
        elif default is None:
            type_val = str  # a number box can't be left empty, so an unset int/float stays text
        else:
            type_val = action.type or type(default)
        ui_params.append(FormParam(name=action.dest, default=default, has_default=True, type_val=type_val,
                                   help_text=action.help or "", is_iterable=is_iterable))
    return ui_params


def _strs(val) -> list[str]:
    return [str(v) for v in val] if isinstance(val, list) else [str(val)]


def form2argv(parser: argparse.ArgumentParser, values: dict) -> list[str]:
    """Command line for *values* (dest -> form value), leaving out empty and default values.

    Positionals go first, so they are not swallowed by a preceding nargs="+" option.
    """
    positionals, options = [], []
    for action in parser._actions:
        val = values.get(action.dest)
        if val is None or val in ("", [], action.default):
            continue
        if not action.option_strings:
            positionals += _strs(val)
            continue
        options.append(action.option_strings[0])
        if isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
            continue  # val differs from the default, so the flag alone says it
        options += _strs(val)
    return positionals + options


class _ParserCaptured(Exception):
    def __init__(self, parser):
        self.parser = parser


def capture_parser(path: Path | str) -> argparse.ArgumentParser:
    """The parser a script builds, got by running it as __main__ up to its parse_args() call.

    The script's imports and any code before parse_args() do run. parse_args is patched on the
    class for the duration, so do not call this concurrently with other argparse users.
    """
    def grab(self, *_args, **_kwargs):
        raise _ParserCaptured(self)

    orig_parse_args, orig_argv = argparse.ArgumentParser.parse_args, sys.argv
    argparse.ArgumentParser.parse_args = grab
    sys.argv = [str(path)]
    try:
        runpy.run_path(str(path), run_name="__main__")
    except _ParserCaptured as captured:
        return captured.parser
    finally:
        argparse.ArgumentParser.parse_args, sys.argv = orig_parse_args, orig_argv
    raise ValueError(f"{path} never called ArgumentParser.parse_args()")
