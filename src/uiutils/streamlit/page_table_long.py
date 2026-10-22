"""Long-table explorer: rows of label columns and one value, filtered, grouped and plotted.

Reads a `.parquet` already in that form (e.g. `geo, tag, batch, field, metric, value`), or a
`.json` turned into it by `json_long` (`level0, level1, ..., value`). Pick an x label and a colour
label; the rows left in each (x, colour) group after the filters are aggregated into one value.
A ratio adds, per label combination, the value under one level of a column over another's
(e.g. tag `LoadNN/NoNNet`), as a new level of that column.
"""

import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from uiutils.json_table import json_long
from uiutils.streamlit.page_files import file_meta
from uiutils.streamlit.slice_view import _drop_stale
from uiutils.streamlit.widgets import filtered_select
from uiutils.textfilter import filter_by_search_query

AGGS = ["mean", "median", "min", "max", "std", "count"]
REGEX_SHOW = 8  # matched levels listed under the regex filter
REGEX_HELP = """Python regex over the chosen column's levels, searched anywhere in the name, ignoring case.

- Anchor for an exact level: `geo1` also matches `synthgeo11`, `^synthgeo1$` does not.
- `|` is OR: `^spe10|synthgeo1$`; a space is AND: `spe10 y90`.
- Exclude with a lookahead: `^(?!HiRes)` keeps every level not starting with HiRes.
- Numbers are matched as text: `^1.$` is batches 10 to 19.
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


def normalize_by_colour(grouped: pd.DataFrame, colour_col: str, val_col: str) -> pd.DataFrame:
    """Divide *val_col* by each *colour_col*'s maximum so each series peaks at 1.0."""
    grouped = grouped.copy()
    maxes = grouped.groupby(colour_col, dropna=False)[val_col].transform("max")
    nonzero = maxes.replace(0, np.nan)
    grouped[val_col] = (grouped[val_col] / nonzero).fillna(grouped[val_col])
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


def render_long_table(root: Path, get_files: Callable[[], list[str]], on_refresh: Callable[[], None]):
    """*get_files()* gives `.parquet`/`.json` paths relative to *root*; the picks are URL-bound."""
    col_ctrl, col_view = st.columns([2, 3])
    with col_ctrl:
        selected = filtered_select("long", "table", get_files(), on_refresh, icon="📈")
        if not selected:
            return
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
    grouped = df.groupby(keys, dropna=False)[value].agg(agg).reset_index()
    if norm and colour:
        grouped = normalize_by_colour(grouped, colour, value)
    # columns renamed: Vega-Lite misreads "/" and "." in field names
    data = pd.DataFrame({"x": grouped[x].astype(str), "v": grouped[value]})
    if colour:
        data["c"] = grouped[colour].astype(str)
    with col_view:
        if data.empty:
            st.info("No rows match the filters.")
            return
        chart = st.bar_chart if kind == "bar" else st.line_chart
        extra = {"stack": False, "sort": False} if kind == "bar" else {}
        averaged = [c for c in labels if c not in keys]
        const = [c for c in averaged if (df[c] == df[c].iloc[0]).all()]  # one category left: named by its value
        single = [str(df[c].iloc[0]) for c in const]  # "mean gradp over geo metric"
        many = [c for c in averaged if c not in const]
        y_label = " ".join([*(["normalized"] if norm and colour else []), agg, *single, *(["over", *many] if many else [])])
        chart(data, x="x", y="v", color="c" if colour else None, x_label=x, y_label=y_label, height=600, **extra)  # streamlit's default is 300
    pivoted = grouped.pivot_table(index=x, columns=colour, values=value) if colour else grouped.set_index(x)
    st.dataframe(pivoted)
    if colour and pivoted.shape[1] >= 2 and len(pivoted) >= 3:
        with st.expander(f"Correlation matrix of {colour} (across {x})"):
            corr = pivoted.corr()
            st.dataframe(corr.style.background_gradient(cmap="coolwarm", vmin=-1.0, vmax=1.0).format("{:.3f}", na_rep="-"))
