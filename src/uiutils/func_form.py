"""Python function signature <-> form fields <-> kwargs, without a GUI framework.

`func2uiparams` turns a function's annotated parameters into FormParams for a form renderer, and
`form2kwargs` casts the form's values back by those annotations. `import_target` resolves a
`"module:func"` string, so a registry can name functions and import them only when picked.
"""

import importlib
import inspect
import json
import types
import typing
from collections.abc import Callable

from uiutils.argparse_form import FormParam, parser2uiparams


def import_target(target: str):
    """The attribute *func* of module *module*, for a `"module:func"` string."""
    module, func = target.split(":")
    return getattr(importlib.import_module(module), func)


def _is_list(ann) -> bool:
    return ann in (list, tuple) or typing.get_origin(ann) in (list, tuple)


def func2uiparams(func, defaults_of: Callable[[], dict[str, FormParam]] | None = None) -> list[FormParam]:
    """One FormParam per parameter of *func*, typed by its annotation (str when unannotated).

    `Annotated[str, "hint"]` gives `type_val="hint"`, for a custom widget in the renderer.
    *defaults_of()* returns {name: FormParam} whose default and help override the signature's,
    e.g. `parser_defaults` for a function that also has an argparse CLI. Raises ValueError or
    TypeError when *func* has no signature (e.g. some C extensions).
    """
    overrides = defaults_of() if defaults_of else {}
    params = []
    for name, p in inspect.signature(func).parameters.items():
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        ann = str if p.annotation is p.empty else p.annotation
        hint = getattr(ann, "__metadata__", None)
        default = None if p.default is p.empty else p.default
        help_text = ""
        if name in overrides:
            default, help_text = overrides[name].default, overrides[name].help_text
        params.append(FormParam(name=name, default=default, has_default=p.default is not p.empty,
                                type_val=hint[0] if hint else ann, help_text=help_text, is_iterable=_is_list(ann)))
    return params


def parser_defaults(parser_target: str) -> Callable[[], dict[str, FormParam]]:
    """A `defaults_of` for func2uiparams: the options of the parser `"module:build_parser"()` returns."""
    def defaults():
        return {p.name: p for p in parser2uiparams(import_target(parser_target)())}
    return defaults


def _cast(ann, val):
    """*val* (a widget value: str, number, bool or list of str) as annotation *ann*; ValueError if it cannot be."""
    if getattr(ann, "__metadata__", None):  # Annotated[X, ...] -> X
        ann = typing.get_args(ann)[0]
    origin, args = typing.get_origin(ann), typing.get_args(ann)
    if origin in (typing.Union, types.UnionType):  # first member that takes the value, e.g. int of int | Generator | None
        for member in args:
            if member is not type(None):
                try:
                    return _cast(member, val)
                except (TypeError, ValueError):
                    continue
        raise ValueError(f"{val!r} is none of {ann}")
    if _is_list(ann):
        if isinstance(val, str):  # a text box, e.g. for `list | None`: JSON, as argparse type=json.loads takes
            val = json.loads(val)
        elem = args[0] if args and args[0] is not Ellipsis else None
        items = [_cast(elem, v) for v in val] if elem else list(val)
        return tuple(items) if (origin or ann) is tuple else items
    if ann is bool and isinstance(val, str):  # from a text box, e.g. for `bool | None`
        return val.strip().lower() in ("1", "true", "yes")
    if ann in (bool, int, float):
        return val if type(val) is ann else ann(val)
    if ann is str or ann is None:
        return val
    raise TypeError(f"no cast to {ann}")


def form2kwargs(params: list[FormParam], values: dict) -> dict:
    """Keyword arguments for *values* (name -> widget value), cast by each param's annotation.

    Empty values are left out, so the function's own default applies. Raises ValueError (incl.
    json.JSONDecodeError) for a value its annotation cannot take.
    """
    kwargs = {}
    for p in params:
        val = values.get(p.name)
        if val is None or val in ("", []):
            continue
        ann = p.type_val if not isinstance(p.type_val, str) else str  # a widget hint: the widget's value
        try:
            kwargs[p.name] = _cast(ann, val)
        except TypeError:  # an annotation without a cast (e.g. a class): pass the widget value on
            kwargs[p.name] = val
    return kwargs
