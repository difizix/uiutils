import argparse
import sys
import types
from typing import Annotated

from uiutils.func_form import form2kwargs, func2uiparams, parser_defaults


def _geo(nx: int = 4, *, sigma: float, hxyz: tuple[float, float, float], k_min: float | None = None,
         drift: list | None = None, seed: int | object | None = None, path: Annotated[str, "file"] = ""):
    return nx, sigma, hxyz, k_min, drift, seed, path


def test_func2uiparams_types_and_hints():
    params = {p.name: p for p in func2uiparams(_geo)}
    assert params["nx"].type_val is int and params["nx"].default == 4
    assert params["sigma"].default is None and not params["sigma"].has_default
    assert params["hxyz"].is_iterable
    assert params["path"].type_val == "file"  # Annotated hint, for a custom widget


def test_form2kwargs_casts_and_leaves_out_empty():
    params = func2uiparams(_geo)
    values = {"nx": 8, "sigma": 1.5, "hxyz": ["1", "2", "0.5"], "k_min": "0.01", "drift": '[{"a": 1}]',
              "seed": "3", "path": "x.npy"}
    assert form2kwargs(params, values) == {"nx": 8, "sigma": 1.5, "hxyz": (1.0, 2.0, 0.5), "k_min": 0.01,
                                           "drift": [{"a": 1}], "seed": 3, "path": "x.npy"}
    assert form2kwargs(params, {"k_min": "", "hxyz": []}) == {}  # the function's defaults apply


def test_parser_defaults_override_signature(monkeypatch):
    def build_parser():
        p = argparse.ArgumentParser()
        p.add_argument("--sigma", type=float, default=1.8, help="std of ln(K)")
        p.add_argument("--seed", type=int, default=None)
        return p

    monkeypatch.setitem(sys.modules, "_fake_cli", types.SimpleNamespace(build_parser=build_parser))
    params = {p.name: p for p in func2uiparams(_geo, defaults_of=parser_defaults("_fake_cli:build_parser"))}
    assert (params["sigma"].default, params["sigma"].help_text) == (1.8, "std of ln(K)")
    assert params["nx"].default == 4  # not in the parser: from the signature
