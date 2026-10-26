"""Long-table explorer: rows of label columns and one value, filtered, grouped and plotted.

Reads a `.parquet` already in that form (e.g. `geo, tag, batch, field, metric, value`), or a
`.json` turned into it by `json_long` (`level0, level1, ..., value`). Pick an x label and a colour
label; the rows left in each (x, colour) group after the filters are aggregated into one value.
An aggregate `centre-err` (`mean-std`, `median-range`) also draws error bars around the centre.
A ratio adds, per label combination, the value under one level of a column over another's
(e.g. tag `LoadNN/NoNNet`), as a new level of that column. A split adds new label columns holding
what a regex's groups capture in a column (e.g. `(\\d+)Infr` on a run name gives the seed).
Presets, named per file-name regex, set the controls from a URL query string when a file is picked.
"""

import json
import re
from collections.abc import Callable
from pathlib import Path
from urllib.parse import parse_qs

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

from uiutils.json_table import json_long
from uiutils.streamlit.page_files import file_meta
from uiutils.streamlit.slice_view import _drop_stale
from uiutils.streamlit.widgets import filtered_select
from uiutils.textfilter import filter_by_search_query

AGGS = ["mean", "median", "min", "max", "std", "count", "mean-std", "median-range"]
NO_MATCH = "not-matched"
# the URL-bound controls a preset sets; the `long_f_<col>` filters are matched by prefix
CONTROLS = ("long_value", "long_rcol", "long_rnum", "long_rden", "long_sp_col", "long_sp", "long_rx_col", "long_rx",
            "long_x", "long_color", "long_agg", "long_chart", "long_norm")
REGEX_SHOW = 8  # matched levels listed under the regex filter
REGEX_HELP = """Python regex over the chosen column's levels, searched anywhere in the name, ignoring case.

- Anchor for an exact level: `geo1` also matches `synthgeo11`, `^synthgeo1$` does not.
- `|` is OR: `^spe10|synthgeo1$`; a space is AND: `spe10 y90`.
- Exclude with a lookahead: `^(?!HiRes)` keeps every level not starting with HiRes.
- Numbers are matched as text: `^1.$` is batches 10 to 19.
"""
SPLIT_HELP = r"""Python regex searched in the chosen column's levels, ignoring case; each capture group becomes a new label column.

- `(\d+)Infr` on `2Infr_run` gives column `<col>_rx1` = `2`; name it with `(?P<seed>\d+)Infr`.
- Levels that do not match (or leave a group unset) get the entry `not-matched`, so they can be picked or filtered.
"""


@st.cache_data(max_entries=8)
def _load(path: str, mtime: float) -> pd.DataFrame:  # noqa: ARG001 -- part of the cache key, so a rewritten file is read again; not _mtime, which st.cache_data would not hash
    if path.endswith(".parquet"):
        df = pd.read_parquet(path)
    else:
        df = pd.DataFrame(json_long(json.loads(Path(path).read_text())))
    # categories as plain labels, so a ratio can add a level and filters see no unused ones
    return df.astype({c: object for c in df.columns if isinstance(df[c].dtype, pd.CategoricalDtype)})


def add_ratio(df: pd.DataFrame, col: str, num, den, value: str = "value") -> pd.DataFrame:
    """*df* plus rows with `col = "num/den"`: per combination of the other columns, the mean value
    under `col == num` over that under `col == den`. Combinations missing either side are dropped;
    a zero denominator gives NaN, not inf."""
    others = [c for c in df.columns if c not in (col, value)]

    def side(level):
        rows = df[df[col] == level]
        return rows.groupby(others, dropna=False)[value].mean() if others else rows[value].mean()

    ratio = (side(num) / side(den)).replace([np.inf, -np.inf], np.nan)
    if not others:
        return pd.concat([df, pd.DataFrame({col: [f"{num}/{den}"], value: [ratio]})], ignore_index=True)
    ratio = ratio.dropna().reset_index().assign(**{col: f"{num}/{den}"})
    return pd.concat([df, ratio[df.columns]], ignore_index=True)


def aggregate(df: pd.DataFrame, keys: list[str], value: str, spec: str) -> pd.DataFrame:
    """One row per *keys* group: *value* aggregated by *spec* (`mean`, ..., or `centre-err`).
    `-std` adds `lo`/`hi` = centre -/+ std (0 for a single row); `-range` adds the group min/max."""
    agg, _, err = spec.partition("-")
    grouped = df.groupby(keys, dropna=False)[value]
    out = grouped.agg(agg).reset_index()
    if err == "std":
        spread = grouped.std().fillna(0.0).to_numpy()
        out["lo"], out["hi"] = out[value] - spread, out[value] + spread
    elif err == "range":
        out["lo"], out["hi"] = grouped.min().to_numpy(), grouped.max().to_numpy()
    return out


def add_split(df: pd.DataFrame, col: str, pattern: str) -> pd.DataFrame:
    """*df* plus one label column per capture group of *pattern* searched in `df[col]` (ignoring case):
    named by the group (`(?P<seed>\\d+)`), else `col_rx1`, `col_rx2`, ...; no group gives the whole
    match as `col_rx`. Rows that do not match, or leave a group unset, get `NO_MATCH`.
    Raises `re.error` for an invalid pattern and `ValueError` for a name already a column."""
    rx = re.compile(pattern, re.IGNORECASE)
    by_index = {i: n for n, i in rx.groupindex.items()}
    names = [by_index.get(k, f"{col}_rx{k}") for k in range(1, rx.groups + 1)] or [f"{col}_rx"]
    if clash := [n for n in names if n in df.columns]:
        raise ValueError(f"column {clash} exists")
    levels = {lv: rx.search(str(lv)) for lv in df[col].unique()}

    def captured(m, k):
        got = m.group(k) if m else None
        return NO_MATCH if got is None else got

    return df.assign(**{n: df[col].map({lv: captured(m, k + 1 if rx.groups else 0) for lv, m in levels.items()})
                        for k, n in enumerate(names)})


def normalize_by_colour(grouped: pd.DataFrame, colour_col: str, val_col: str, also: tuple[str, ...] = ()) -> pd.DataFrame:
    """Divide *val_col* (and the *also* columns, e.g. error bounds) by each *colour_col*'s maximum
    of *val_col* so each series peaks at 1.0."""
    grouped = grouped.copy()
    maxes = grouped.groupby(colour_col, dropna=False)[val_col].transform("max")
    nonzero = maxes.replace(0, np.nan)
    for c in (val_col, *also):
        grouped[c] = (grouped[c] / nonzero).fillna(grouped[c])
    return grouped


def _pick(label: str, options: list, key: str, **kw):
    """URL-bound selectbox that forgets a value not among this file's *options*."""
    _drop_stale(key, lambda v: v in options)
    return st.selectbox(label, options, key=key, bind="query-params", **kw)


def _levels(s: pd.Series) -> list:
    return sorted(s.dropna().unique(), key=lambda v: (not isinstance(v, (int, float)), str(v) if not isinstance(v, (int, float)) else v))


def _filters(df: pd.DataFrame, labels: list[str]) -> pd.DataFrame:
    """A multiselect per label column with 2+ levels (none picked = all), URL-bound as `?long_f_<col>=`."""
    with st.expander("Filters", expanded=True):
        for c in labels:
            levels = _levels(df[c])
            if len(levels) < 2:
                continue
            key = f"long_f_{c}"
            _drop_stale(key, lambda v, levels=levels: all(x in levels for x in v))
            picked = st.multiselect(c, levels, key=key, bind="query-params", placeholder=f"all {len(levels)}")
            if picked:
                df = df[df[c].isin(picked)]
        return _regex_filter(df, labels)


def _split(df: pd.DataFrame, labels: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """"Split in" a label column by a regex into new label columns (see `add_split`); URL-bound as
    `?long_sp_col=` and `?long_sp=`."""
    col_c, rx_c = st.columns([1, 2])
    with col_c:
        col = _pick("Split in", [None, *labels], "long_sp_col", format_func=lambda c: c or "none")
    with rx_c:
        _drop_stale("long_sp", lambda v: isinstance(v, str))
        pattern = st.text_input("Split regex", key="long_sp", bind="query-params", help=SPLIT_HELP, disabled=not col)
    if not col or not pattern.strip():
        return df, labels
    try:
        out = add_split(df, col, pattern)
    except (re.error, ValueError) as e:
        st.caption(f"⚠️ split not applied: {e}")
        return df, labels
    return out, [*labels, *[c for c in out.columns if c not in df.columns]]


def _regex_filter(df: pd.DataFrame, labels: list[str]) -> pd.DataFrame:
    """One label column and a regex over its levels, applied after the multiselects; URL-bound as
    `?long_rx_col=` and `?long_rx=`."""
    col_c, rx_c = st.columns([1, 2])
    with col_c:
        col = _pick("Regex on", [None, *labels], "long_rx_col", format_func=lambda c: c or "none")
    with rx_c:
        _drop_stale("long_rx", lambda v: isinstance(v, str))
        query = st.text_input("Regex", key="long_rx", bind="query-params", help=REGEX_HELP, disabled=not col)
    if not col or not query.strip():
        return df
    levels = _levels(df[col])
    matched, bad = filter_by_search_query(levels, query)
    if bad:
        st.caption("⚠️ invalid regex, not applied")
        return df
    more = f", ... (+{len(matched) - REGEX_SHOW})" if len(matched) > REGEX_SHOW else ""
    st.caption(f"{len(matched)} of {len(levels)}: {', '.join(map(str, matched[:REGEX_SHOW]))}{more}")
    return df[df[col].isin(matched)]


def _chart(data: pd.DataFrame, kind: str, x_label: str, y_label: str, coloured: bool):
    """The bar/line chart of `x`, `v` (colour `c`) in x's data order, with a `lo`-`hi` whisker per point if given."""
    # side by side only if an x holds several colours; a colour derived from x (one per x) would
    # otherwise leave an empty slot per other colour at every x
    grouped = coloured and kind == "bar" and data.groupby("x")["c"].nunique().max() > 1
    # a wider gap between groups, whose bars touch
    x = alt.X("x:N", sort=None, title=x_label, scale=alt.Scale(paddingInner=0.3) if grouped else alt.Undefined)
    enc = {"x": x, "y": alt.Y("v:Q", title=y_label)}
    if coloured:
        enc["color"] = alt.Color("c:N")
    shift = {"xOffset": alt.XOffset("c:N")} if grouped else {}
    base = alt.Chart(data)
    # streamlit's theme sizes a bar to 0.85 of its band; a full band makes a coloured group's bars touch
    bar = base.mark_bar(width=alt.RelativeBandSize(1)) if grouped else base.mark_bar()
    centre = (bar if kind == "bar" else base.mark_line(point=True)).encode(**enc, **shift)
    if "lo" not in data:
        return centre.properties(height=600)
    # a sized bar, not mark_rule: a rule sits at the band's start, so it drifts left of an xOffset bar;
    # mid grey: visible on dark and light themes
    whisker = base.mark_bar(size=2, color="#a0a0a0").encode(x=x, y="lo:Q", y2="hi:Q", **shift)
    return alt.layer(centre, whisker).properties(height=600)


def parse_preset(query: str) -> dict:
    """Control values from a metrics URL query (`long_color=field&long_f_tag=A%2FB...`): the
    `long_f_*` filters as lists, `true`/`false` as bools; the file pick (`long`, `longq`) is dropped."""
    out = {}
    for k, vals in parse_qs(query.lstrip("?")).items():
        if k in CONTROLS:
            v = vals[-1]
            out[k] = {"true": True, "false": False}.get(v.lower(), v)
        elif k.startswith("long_f_"):
            out[k] = vals
    return out


def _set_controls(values: dict):
    for k in [k for k in st.session_state if k in CONTROLS or str(k).startswith("long_f_")]:
        del st.session_state[k]
    st.session_state.update(values)


def _preset(selected: str, presets: dict[str, dict[str, str]]):
    """"Select preset" over the named presets of every file regex that *selected* matches; switching
    file applies the first one, unless a pasted URL (first run) already sets the controls."""
    named = {n: q for rx, group in presets.items() if re.search(rx, selected) for n, q in group.items()}
    if not named:
        return
    names = [None, *named]
    _drop_stale("long_preset", lambda v: v in names)
    if st.session_state.get("long_preset_for") != selected:
        first_run = "long_preset_for" not in st.session_state
        st.session_state.long_preset_for = selected
        url_set = any(k in CONTROLS or k.startswith("long_f_") for k in st.query_params)
        if not (first_run and url_set):
            if not (first_run and st.session_state.get("long_preset")):  # else: the URL's ?long_preset=
                st.session_state.long_preset = names[1]
            _set_controls(parse_preset(named[st.session_state.long_preset]))

    def apply():
        if st.session_state.long_preset:
            _set_controls(parse_preset(named[st.session_state.long_preset]))

    st.selectbox("Select preset", names, key="long_preset", bind="query-params", on_change=apply,
                 format_func=lambda n: n or "none", help="Sets the controls below; they can be changed after")


def render_long_table(root: Path, get_files: Callable[[], list[str]], on_refresh: Callable[[], None],
                      presets: dict[str, dict[str, str]] | None = None):
    """*get_files()* gives `.parquet`/`.json` paths relative to *root*; the picks are URL-bound.
    *presets*: file-path regex -> {preset name: metrics URL query}, see `parse_preset`."""
    col_ctrl, col_view = st.columns([2, 3])
    with col_ctrl:
        selected = filtered_select("long", "table", get_files(), on_refresh, icon="📈")
        if not selected:
            return
        if presets:
            _preset(selected, presets)
        path = Path(root) / selected
        try:
            st.caption(file_meta(path))
            df = _load(str(path), path.stat().st_mtime)
        except (OSError, ValueError) as e:
            st.error(f"Cannot read `{selected}`: {e}")
            return
        numeric = [c for c in df.columns if pd.api.types.is_float_dtype(df[c])]
        if not numeric or len(df.columns) < 2:
            st.info("Needs a float value column and at least one label column.")
            return
        value = _pick("Value", numeric, "long_value", index=numeric.index("value") if "value" in numeric else 0)
        labels = [c for c in df.columns if c != value]
        df = df[[*labels, value]]

        r_col, r_num, r_den = st.columns(3)
        with r_col:
            ratio_col = _pick("Ratio in", [None, *labels], "long_rcol", format_func=lambda c: c or "none")
        if ratio_col:
            levels = _levels(df[ratio_col])
            with r_num:
                num = _pick("numerator", levels, "long_rnum")
            with r_den:
                den = _pick("denominator", levels, "long_rden", index=min(1, len(levels) - 1))
            if num != den:
                df = add_ratio(df, ratio_col, num, den, value)

        df, labels = _split(df, labels)
        df = _filters(df, labels)
        x_c, c_c, a_c = st.columns(3)
        with x_c:
            x = _pick("x", labels, "long_x", index=labels.index(df[labels].nunique().idxmax()))  # default: the level with most entries
        with c_c:
            colour = _pick("Colour", [None, *[c for c in labels if c != x]], "long_color",
                           format_func=lambda c: c or "none")
        with a_c:
            agg = _pick("Aggregate", AGGS, "long_agg")
        k_c, n_c = st.columns([2, 1], vertical_alignment="bottom")
        with k_c:
            kind = st.radio("Chart", ["bar", "line"], horizontal=True, key="long_chart", bind="query-params")
        with n_c:
            norm = st.checkbox("Normalize y", key="long_norm", bind="query-params", disabled=not colour,
                               help="Scale each colour series by its maximum so peaks equal 1.0")
        st.caption(f"{len(df)} rows after filters")

    keys = [x, colour] if colour else [x]
    grouped = aggregate(df, keys, value, agg)
    bars = [c for c in ("lo", "hi") if c in grouped]
    if norm and colour:
        grouped = normalize_by_colour(grouped, colour, value, tuple(bars))
    # columns renamed: Vega-Lite misreads "/" and "." in field names
    data = pd.DataFrame({"x": grouped[x].astype(str), "v": grouped[value], **{c: grouped[c] for c in bars}})
    if colour:
        data["c"] = grouped[colour].astype(str)
    with col_view:
        if data.empty:
            st.info("No rows match the filters.")
            return
        averaged = [c for c in labels if c not in keys]
        const = [c for c in averaged if (df[c] == df[c].iloc[0]).all()]  # one category left: named by its value
        single = [str(df[c].iloc[0]) for c in const]  # "mean gradp over geo metric"
        many = [c for c in averaged if c not in const]
        y_label = " ".join([*(["normalized"] if norm and colour else []), agg, *single, *(["over", *many] if many else [])])
        if kind == "bar" or bars:
            st.altair_chart(_chart(data, kind, x, y_label, bool(colour)), width="stretch")
        else:
            st.line_chart(data, x="x", y="v", color="c" if colour else None, x_label=x, y_label=y_label, height=600)
    pivoted = grouped.pivot_table(index=x, columns=colour, values=value) if colour else grouped.set_index(x)[[value]]
    st.dataframe(pivoted)
    if colour and pivoted.shape[1] >= 2 and len(pivoted) >= 3:
        with st.expander(f"Correlation matrix of {colour} (across {x})"):
            corr = pivoted.corr()
            st.dataframe(corr.style.background_gradient(cmap="coolwarm", vmin=-1.0, vmax=1.0).format("{:.3f}", na_rep="-"))
