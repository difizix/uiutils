"""Slice viewer for an n-d numpy array: leading indices down to 3-d, then a normal axis and a slice.

Only numpy and Pillow (a streamlit dependency), so apps can view arrays without an image library.
Axes are numbered unless the caller names them: layouts differ between apps ((nz, ny, nx) vs (nx, ny, nz)).
"""

import numpy as np
import streamlit as st
from PIL import Image

# Small grids are upscaled (nearest) to about this many pixels on the long side, so the browser
# stretches them without blurring the cells.
VIEW_PX = 512

# "gray" without axes is drawn without matplotlib
CMAPS = ["gray", "viridis", "magma", "turbo", "coolwarm"]


def _drop_stale(key, ok):
    """Forget a widget value left from another array or a pasted URL, so the default applies again."""
    if key in st.session_state and not ok(st.session_state[key]):
        del st.session_state[key]


def _index_slider(label, n, key):
    """Slider over range(n), URL-bound, defaulting to the middle; 0 without a widget when n == 1."""
    if n <= 1:
        return 0
    _drop_stale(key, lambda v: isinstance(v, int) and 0 <= v < n)
    return st.slider(label, 0, n - 1, n // 2, key=key, bind="query-params")


def _to_image(slice_2d, lo, hi):
    """Grayscale PIL image of *slice_2d* with [lo, hi] mapped to [0, 255]; NaNs are black."""
    scaled = (slice_2d - lo) / (hi - lo) if hi > lo else np.zeros(slice_2d.shape)
    gray = (np.nan_to_num(np.clip(scaled, 0, 1)) * 255).astype(np.uint8)
    img = Image.fromarray(gray)
    f = max(1, VIEW_PX // max(gray.shape))
    return img.resize((img.width * f, img.height * f), Image.Resampling.NEAREST)


def _plot(slice_2d, lo, hi, cmap, axis_labels, value_label):
    """*slice_2d* through matplotlib (imported only when asked for); *axis_labels* None hides the axes and
    the colorbar."""
    from matplotlib.figure import Figure  # noqa: PLC0415 -- optional dependency, only for this view

    nr, nc = slice_2d.shape
    h = min(8, max(2.5, 6 * nr / nc))  # inches; the width follows the slice's aspect, plus room for the colorbar
    fig = Figure(figsize=(min(6, max(3.5, h * nc / nr + 1.5)), h), layout="constrained")
    ax = fig.subplots()
    im = ax.imshow(slice_2d, vmin=lo, vmax=hi, cmap=cmap, interpolation="nearest", aspect="equal")
    if axis_labels:
        ax.set_ylabel(axis_labels[0])
        ax.set_xlabel(axis_labels[1])
        fig.colorbar(im, ax=ax, label=value_label, shrink=0.8)
    else:
        ax.set_axis_off()
    return fig


def render_slices(arr, key_prefix: str, axis_names=None, info: str = "", cols=None):
    """View *arr* as controls and an image, in *cols* = (controls, view) containers or two new columns.

    Widgets are URL-bound as `<key_prefix><name>` (`axis`, `slice`, `log`, ...). *axis_names* name arr's
    axes (e.g. "XYZ"; default their numbers), *info* is appended to the image caption. Size-1 axes are
    dropped first, so e.g. a (3, 1, 20, 100) array is viewed as (3, 20, 100), its axes 0, 2, 3.
    """
    arr = np.asarray(arr)
    col_ctrl, col_view = cols or st.columns([2, 3])
    col_ctrl.caption(f"shape `{arr.shape}` `{arr.dtype}`")
    if arr.dtype.names and arr.ndim == 1:  # record array, e.g. a well-rate history: one column per field
        col_view.dataframe({n: arr[n] for n in arr.dtype.names})
        return
    if arr.dtype.kind not in "biuf":
        col_view.warning(f"Cannot view dtype `{arr.dtype}`.")
        return
    names = list(axis_names) if axis_names else [str(i) for i in range(arr.ndim)]
    names = [nm for nm, n in zip(names, arr.shape, strict=True) if n != 1]
    arr = np.squeeze(arr)
    if arr.dtype.kind == "b":
        arr = arr.astype(np.uint8)
    if arr.ndim == 0:
        col_view.write(f"value: `{arr.item()}`")
        return
    if arr.ndim == 1:
        col_view.line_chart(arr)
        return

    def label(nm):
        return nm if axis_names else f"axis {nm}"

    with col_ctrl:
        for d in range(arr.ndim - 3):  # leading axes: fix an index on each
            arr = arr[_index_slider(f"Index on {label(names[d])} (n={arr.shape[0]})", arr.shape[0], f"{key_prefix}i{d}")]
        names = names[-arr.ndim:]
        where = ""
        if arr.ndim == 3:
            key = f"{key_prefix}axis"
            _drop_stale(key, lambda v: v in names)
            thinnest = 2 - int(np.argmin(arr.shape[::-1]))  # default; ties go to the last axis (Z of a cube)
            normal = st.selectbox("Normal axis", names, index=thinnest, key=key,
                                  format_func=lambda nm: f"{label(nm)} (n={arr.shape[names.index(nm)]})",
                                  bind="query-params")
            axis = names.index(normal)
            idx = _index_slider("Slice index", arr.shape[axis], f"{key_prefix}slice")
            slice_2d = np.take(arr, idx, axis=axis)
            shown = [a for a in range(3) if a != axis]
            where = f"`{label(normal)}` @ `{idx}` / `{arr.shape[axis] - 1}` │ "
        else:
            slice_2d, shown = arr, [0, 1]
        axis_labels = [f"{label(names[a])} (n={arr.shape[a]})" for a in shown]
        slice_2d = slice_2d.astype(np.float64)

        # log10 for fields spanning decades (e.g. permeability); values <= 0 clamp to the smallest positive
        log = st.checkbox("Log10 scale", key=f"{key_prefix}log", bind="query-params") and (arr > 0).any()
        if log:
            tiny = arr[arr > 0].min()
            arr, slice_2d = np.log10(np.maximum(arr, tiny)), np.log10(np.maximum(slice_2d, tiny))

        finite = arr[np.isfinite(arr)]
        lo, hi = (float(finite.min()), float(finite.max())) if finite.size else (0.0, 0.0)
        if hi > lo:  # the colour range spans the whole (index-fixed) array, so slices compare
            # in % of [lo, hi]: a slider over the values themselves breaks for tiny ones (k ~ 1e-12 m^2)
            p0, p1 = st.slider("Colour range (% of min-max)", 0.0, 100.0, (0.0, 100.0), step=0.5,
                               key=f"{key_prefix}range")
            lo, hi = lo + (hi - lo) * p0 / 100, lo + (hi - lo) * p1 / 100
        c_map, c_axes, c_tr = st.columns([2, 2, 1], vertical_alignment="bottom")
        _drop_stale(f"{key_prefix}cmap", lambda v: v in CMAPS)
        cmap = c_map.selectbox("Colormap", CMAPS, key=f"{key_prefix}cmap", bind="query-params")
        with_axes = c_axes.checkbox("Axes & colorbar", key=f"{key_prefix}axes", bind="query-params")
        if c_tr.checkbox("Transpose", key=f"{key_prefix}T", bind="query-params"):  # swap the slice's rows and columns
            slice_2d, axis_labels = slice_2d.T, axis_labels[::-1]
        st.caption(f"slice min `{np.nanmin(slice_2d):.4g}` max `{np.nanmax(slice_2d):.4g}`"
                   f" mean `{np.nanmean(slice_2d):.4g}`")

    caption = f"{where}`{slice_2d.shape}` │ colour: `{lo:.4g}` to `{hi:.4g}`" + (f" │ {info}" if info else "")
    with col_view:
        if with_axes or cmap != "gray":
            st.pyplot(_plot(slice_2d, lo, hi, cmap, axis_labels if with_axes else None,
                            "log10(value)" if log else "value"), width="content")
            st.caption(caption)
        else:
            st.image(_to_image(slice_2d, lo, hi), width="stretch", caption=caption)
