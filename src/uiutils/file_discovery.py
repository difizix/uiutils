"""Find the files a GUI lists: plots, logs and markdown reports.

Paths are returned as `str`, relative to *root*, newest first. App-specific rules (which run
directories hold duplicates, which are too big to walk) come in as `prune`/`keep` callables.
"""

import os
from collections.abc import Callable, Iterator
from pathlib import Path

# Caches, virtualenvs and editor scratch dirs. Matched on exact directory name, so "tmp-"
# excludes a directory literally called `tmp-`, not every name starting with "tmp-".
EXCLUDE_DIRS = frozenset({".git", ".venv", "__pycache__", ".deps", ".ruff_cache", ".antigravity", "tmp-"})

# Reports additionally skip `.agents`, which holds agent plans/rules rather than project docs.
REPORT_EXCLUDE_DIRS = EXCLUDE_DIRS | {".agents"}

# The depth cap keeps the glob off deep run/checkpoint trees.
REPORT_PATTERNS = ("*.md", "*/*.md", "*/*/*.md")


def walk_files(root: Path, prune: Callable[[Path], bool] | None = None) -> Iterator[Path]:
    """Files under *root*, relative to it.

    Excluded and pruned directories are never entered, which is what keeps this fast on trees
    with millions of checkpoint files. `prune(rel_dir)` gets the directory relative to *root*.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not (prune and prune(rel / d))]
        for name in filenames:
            yield rel / name


def is_log(path: Path) -> bool:
    return path.suffix == ".log" or path.name in {"log", "log-"} or path.name.startswith("log_")


def mtime_sorted(root: Path, paths: list[Path]) -> list[str]:
    """Newest first, name as tie-break; unstat-able paths sort last."""
    def sort_key(p: Path):
        try:
            return (-(root / p).stat().st_mtime, str(p))
        except OSError:
            return (0, str(p))

    return [str(p) for p in sorted(paths, key=sort_key)]


def find_outputs(root: Path, prune: Callable[[Path], bool] | None = None,
                 keep: Callable[[Path], bool] | None = None) -> tuple[list[str], list[str]]:
    """Every plot and log under *root*, as `(pngs, logs)`; `keep(rel_path)` drops unwanted files."""
    root = Path(root)
    png_files: list[Path] = []
    log_files: list[Path] = []
    for path in walk_files(root, prune):
        if keep and not keep(path):
            continue
        if path.suffix == ".png":
            png_files.append(path)
        elif is_log(path):
            log_files.append(path)
    return mtime_sorted(root, png_files), mtime_sorted(root, log_files)


def find_reports(root: Path) -> list[str]:
    """Markdown files at most three path components below *root*, newest first."""
    root = Path(root)
    md_files = [
        path.relative_to(root)
        for pattern in REPORT_PATTERNS
        for path in root.glob(pattern)
        if path.is_file() and not REPORT_EXCLUDE_DIRS.intersection(path.relative_to(root).parts[:-1])
    ]
    return mtime_sorted(root, md_files)
