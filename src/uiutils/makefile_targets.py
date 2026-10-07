"""Read a Makefile's runnable targets and its user-overridable (`?=`) variables.

A small regex reader, not a make implementation: no includes, conditionals or variable
expansion. Enough to list targets in a GUI and run them as `make <target> VAR=value`.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

# "name [name2]: [prereqs] [# doc]", but not "VAR := value" or "a::b"
_TARGET_RE = re.compile(r"^([^\s#=:][^#=:]*?)\s*:(?![=:])(.*)$")
_VAR_RE = re.compile(r"^([A-Za-z_]\w*)\s*\?=\s*(.*)$")


@dataclass
class MakeTarget:
    name: str
    doc: str  # inline "# ..." after the colon, else the comment block right above
    recipe: list[str] = field(default_factory=list)


def _logical_lines(text: str) -> list[str]:
    """Join backslash-continued lines."""
    return re.sub(r"[ \t]*\\\n[ \t]*", " ", text).splitlines()


def parse_makefile(path: Path | str) -> tuple[list[MakeTarget], dict[str, str]]:
    """Return the Makefile's targets in file order, and its `?=` variables with their defaults."""
    targets: list[MakeTarget] = []
    variables: dict[str, str] = {}
    comments: list[str] = []
    current: list[MakeTarget] = []  # targets the following recipe lines belong to

    for line in _logical_lines(Path(path).read_text()):
        if line.startswith("\t"):
            for tgt in current:
                tgt.recipe.append(line[1:])
            continue
        stripped = line.strip()
        if not stripped:
            comments = []
            continue
        if stripped.startswith("#"):
            comments.append(stripped.lstrip("#").strip())
            continue

        current = []
        if m := _VAR_RE.match(line):
            variables[m[1]] = m[2].strip()
        elif m := _TARGET_RE.match(line):
            names = m[1].split()
            if all(n.startswith(".") for n in names):
                continue  # .PHONY & co: keep the comment block for the target below
            doc = m[2].partition("#")[2].strip() or "\n".join(comments)
            current = [MakeTarget(n, doc) for n in names if "%" not in n and "$" not in n]
            targets.extend(current)
        comments = []

    return targets, variables
