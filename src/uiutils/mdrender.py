"""Markdown preprocessing for a Streamlit report viewer: inline images, in-app links, mermaid blocks.

Nothing here renders: the functions rewrite or split markdown so the caller (`st.markdown` plus
a mermaid iframe, say) can display it. In-app links follow one convention: the app's docs page
is served at `docs` and binds its selection to the `doc` query parameter, so a link to a
markdown file becomes `docs?doc=<path relative to root>`.
"""

import base64
import html
import mimetypes
import re
from pathlib import Path
from urllib.parse import quote

_IMAGE_RE = re.compile(r"!\[(.*?)\]\((.*?)\)")
LINK_RE = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)\s]+)\)")  # not images
_LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s")
_LINK_SEPARATORS = " \t,;."
_MERMAID_RE = re.compile(r"```mermaid\s*\n(.*?)\n```", re.DOTALL)


def resolve_markdown_images(md_content: str, base_dir: Path) -> str:
    """Inline every local `![alt](src)` image as a data URI.

    *src* is resolved against *base_dir* (the markdown file's own directory), so a report can
    reference figures sitting next to it. Remote (`http://`, `https://`) and already-inlined
    (`data:`) sources pass through, as does anything that does not resolve to a file -- a broken
    path stays a broken link rather than raising.

    Only markdown image syntax is rewritten. A raw `<img src="...">` is left alone and will not
    load in a viewer that serves no static files.
    """
    base_dir = Path(base_dir)

    def replace_match(match: re.Match) -> str:
        alt, src_part = match.group(1), match.group(2).strip()
        if not src_part:
            return match.group(0)
        # Drop any markdown title suffix: ![a](x.png "title")
        src = src_part.split()[0].strip("\"'")

        if src.startswith(("http://", "https://", "data:")):
            return match.group(0)

        img_path = (base_dir / src).resolve()
        if not (img_path.exists() and img_path.is_file()):
            return match.group(0)

        try:
            if img_path.suffix.lower() == ".svg":
                svg_data = img_path.read_text(encoding="utf-8", errors="ignore")
                # URL-encode rather than base64 so '#' in fill colours cannot end the URI early.
                return f"![{alt}](data:image/svg+xml;utf8,{quote(svg_data)})"
            mime_type = mimetypes.guess_type(str(img_path))[0] or "image/png"
            encoded = base64.b64encode(img_path.read_bytes()).decode("utf-8")
        except OSError:
            return match.group(0)
        return f"![{alt}](data:{mime_type};base64,{encoded})"

    return _IMAGE_RE.sub(replace_match, md_content)


def gui_href(href: str, base_dir: Path, root: Path) -> str | None:
    """The in-app route a markdown link points to, or None if it isn't one.

    A relative `.md` link is resolved against *base_dir* and becomes `docs?doc=<path relative to
    root>`, the docs page's bound query parameter. A link that already is a GUI route (contains
    `?`, e.g. `logs?log=runs/log.run_x`) is returned as is. External links, anchors and links that
    don't resolve to a markdown file under *root* give None.
    """
    if href.startswith(("http://", "https://", "mailto:", "#")):
        return None
    if "?" in href:
        return href
    root = Path(root).resolve()
    path = (Path(base_dir) / href.split("#", maxsplit=1)[0]).resolve()
    if path.suffix != ".md" or not path.is_file() or not path.is_relative_to(root):
        return None
    return f"docs?doc={quote(str(path.relative_to(root)), safe='/')}"


def split_trailing_links(line: str, base_dir: Path, root: Path) -> tuple[str, list[tuple[str, str]]]:
    """Split a list item, or a line of only links, into its text and its trailing in-app links.

    Trailing links are links to in-app routes (see `gui_href`) at the end of the line, separated only
    by spaces, commas, semicolons or periods; they come back as `(label, route)`. Any other line (prose,
    table rows, items whose links sit mid-text) comes back unchanged with no links: pulling a link
    out of it would leave a hole in the sentence or cell.
    """
    links: list[tuple[str, str]] = []
    end = len(line)
    for m in reversed(list(LINK_RE.finditer(line))):
        route = gui_href(m.group(2), base_dir, root)
        if route is None or line[m.end():end].strip(_LINK_SEPARATORS):
            break
        links.append((m.group(1), route))
        end = m.start()
    text = line[:end].rstrip(_LINK_SEPARATORS)
    if not links or not (_LIST_ITEM_RE.match(line) or not text.strip()):
        return line, []
    return text, links[::-1]


def resolve_markdown_links(md_content: str, base_dir: Path, root: Path) -> str:
    """Rewrite links to in-app routes (see `gui_href`) as same-tab `<a>` tags; leave the rest.

    `target="_self"` overrides streamlit's default new tab, which would start a new session.
    """
    def replace_match(match: re.Match) -> str:
        text, href = match.group(1), match.group(2)
        route = gui_href(href, base_dir, root)
        return match.group(0) if route is None else f'<a href="{html.escape(route)}" target="_self">{text}</a>'

    return LINK_RE.sub(replace_match, md_content)


def split_mermaid_blocks(md_content: str) -> list[tuple[str, str]]:
    """Split markdown into ordered `("markdown" | "mermaid", text)` segments.

    Mermaid fences need a different renderer from the surrounding prose, so they are separated
    out here and the caller decides how to draw each kind. Always returns at least one segment.
    """
    parts: list[tuple[str, str]] = []
    last_end = 0
    for match in _MERMAID_RE.finditer(md_content):
        start, end = match.span()
        if start > last_end:
            parts.append(("markdown", md_content[last_end:start]))
        parts.append(("mermaid", match.group(1).strip()))
        last_end = end

    if last_end < len(md_content):
        parts.append(("markdown", md_content[last_end:]))

    return parts or [("markdown", md_content)]
