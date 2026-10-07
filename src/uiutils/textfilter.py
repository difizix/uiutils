"""Text helpers behind the GUI file pickers and viewers: regex filtering, wrap-around neighbours, line filters.

Free of streamlit, so the filtering rules are testable and every picker filters the same way.
"""

import re


def filter_by_search_query(file_list, query_str) -> tuple[list, bool]:
    """Filter items (strings or Paths) by a whitespace-separated query string.

    Each term is applied as a case-insensitive regex search and the terms are AND-ed. A bad
    regex yields `([], True)` rather than raising, so callers can report it however they like.
    """
    if not query_str or not query_str.strip():
        return list(file_list), False

    filtered = list(file_list)
    for term in query_str.split():
        try:
            pattern = re.compile(term.strip(), re.IGNORECASE)
        except re.error:
            return [], True
        filtered = [f for f in filtered if pattern.search(str(f))]

    return filtered, False


def cycle_neighbors(items: list, current) -> tuple:
    """The items before and after *current*, wrapping around at both ends.

    Returns `(None, None)` for an empty list. When *current* is not in the list -- a stale
    selection -- both neighbours are the first item, so either button resets to a valid choice.
    """
    if not items:
        return None, None
    try:
        idx = items.index(current)
    except ValueError:
        return items[0], items[0]
    return items[(idx - 1) % len(items)], items[(idx + 1) % len(items)]


def filter_lines(text: str, keep: str, remove: str) -> list[str]:
    """Lines of *text* containing every *keep* term and none of the *remove* terms.

    Terms are whitespace-separated plain substrings (not regexes), matched case-insensitively;
    an empty *keep* keeps every line.
    """
    keep_terms, remove_terms = keep.lower().split(), remove.lower().split()
    return [line for line in text.splitlines()
            if all(t in line.lower() for t in keep_terms) and not any(t in line.lower() for t in remove_terms)]
