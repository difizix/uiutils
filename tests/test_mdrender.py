import base64

from uiutils.mdrender import (
    gui_href,
    is_table_separator,
    resolve_markdown_images,
    resolve_markdown_links,
    split_cell_links,
    split_mermaid_blocks,
    split_table_row,
    split_trailing_links,
)

# A 1x1 transparent PNG -- small enough to inline, real enough for mimetypes to identify.
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


def test_resolve_markdown_images_inlines_png_and_svg(tmp_path):
    (tmp_path / "fig.png").write_bytes(PNG_1X1)
    (tmp_path / "d.svg").write_text('<svg><rect fill="#ff0000"/></svg>')

    out = resolve_markdown_images("![a](./fig.png)\n![b](d.svg)\n", tmp_path)

    assert "data:image/png;base64," in out
    # SVG is url-encoded, not base64, so a '#' cannot terminate the URI early.
    assert "data:image/svg+xml;utf8," in out
    assert "%23ff0000" in out
    assert "base64" not in out.split("svg+xml")[1]


def test_resolve_markdown_images_passthrough_cases(tmp_path):
    src = (
        "![r](https://example.com/x.png)\n"
        "![d](data:image/png;base64,AAAA)\n"
        "![missing](./nope.png)\n"
        "![empty]()\n"
    )
    assert resolve_markdown_images(src, tmp_path) == src


def test_resolve_markdown_images_strips_title_suffix(tmp_path):
    (tmp_path / "fig.png").write_bytes(PNG_1X1)
    out = resolve_markdown_images('![a](fig.png "the title")', tmp_path)
    assert "data:image/png;base64," in out


def test_resolve_markdown_links_targets_docs_page(tmp_path):
    (tmp_path / "plans").mkdir()
    (tmp_path / "plans" / "p.md").write_text("x")
    src = "[p](p.md#s) [g](logs?log=a) [w](https://x.y) [m](nope.md) ![i](p.png)"
    out = resolve_markdown_links(src, tmp_path / "plans", tmp_path)
    assert out == ('<a href="docs?doc=plans/p.md" target="_self">p</a> '
                   '<a href="logs?log=a" target="_self">g</a> [w](https://x.y) [m](nope.md) ![i](p.png)')


def test_split_trailing_links_only_from_items_ending_in_links(tmp_path):
    (tmp_path / "p.md").write_text("x")
    assert split_trailing_links("- run [log](logs?log=a), [p](p.md)", tmp_path, tmp_path) == (
        "- run", [("log", "logs?log=a"), ("p", "docs?doc=p.md")])
    assert split_trailing_links("[p](p.md),", tmp_path, tmp_path) == ("", [("p", "docs?doc=p.md")])
    assert split_trailing_links("hwNaga: [p](p.md) [log](logs?log=a)", tmp_path, tmp_path) == (
        "hwNaga:", [("p", "docs?doc=p.md"), ("log", "logs?log=a")])
    for kept in ("see [p](p.md) here", "text ending [p](p.md)", "| a | [p](p.md) |", "- web [w](https://x.y)"):
        assert split_trailing_links(kept, tmp_path, tmp_path) == (kept, [])


def test_split_table_row_keeps_escaped_and_code_pipes():
    assert split_table_row(r"| a | b \| c | `x|y` |") == ["a", r"b \| c", "`x|y`"]
    assert split_table_row("a | b") == ["a", "b"]
    assert split_table_row("| a || c |") == ["a", "", "c"]
    assert is_table_separator("|---|:--:|")
    assert is_table_separator("--- | ---")
    assert not is_table_separator("---")
    assert not is_table_separator("| a |")


def test_split_cell_links_segments_in_order(tmp_path):
    (tmp_path / "p.md").write_text("x")
    cell = "see [p](p.md), [log](logs?log=a) and [w](https://x.y)"
    assert split_cell_links(cell, tmp_path, tmp_path) == [
        ("see", None), ("p", "docs?doc=p.md"), ("log", "logs?log=a"), ("and [w](https://x.y)", None)]
    assert split_cell_links("plain", tmp_path, tmp_path) == [("plain", None)]
    assert split_cell_links("", tmp_path, tmp_path) == [("", None)]


def test_gui_href_strips_local_origin_only(tmp_path):
    assert gui_href("http://localhost:8501/metrics?a=1&b=2", tmp_path, tmp_path) == "metrics?a=1&b=2"
    assert gui_href("https://127.0.0.1/logs?x=1", tmp_path, tmp_path) == "logs?x=1"
    assert gui_href("/studio?studio_file=a.py", tmp_path, tmp_path) == "studio?studio_file=a.py"
    assert gui_href("http://example.com/metrics?a=1", tmp_path, tmp_path) is None


def test_split_mermaid_blocks_preserves_order():
    md = "intro\n```mermaid\ngraph TD\n  A-->B\n```\nmiddle\n```mermaid\ngraph LR\n```\ntail"
    parts = split_mermaid_blocks(md)

    assert [kind for kind, _ in parts] == [
        "markdown", "mermaid", "markdown", "mermaid", "markdown",
    ]
    assert parts[1][1] == "graph TD\n  A-->B"
    assert parts[2][1].strip() == "middle"


def test_split_mermaid_blocks_without_fences_returns_one_segment():
    assert split_mermaid_blocks("plain") == [("markdown", "plain")]
    assert split_mermaid_blocks("") == [("markdown", "")]
