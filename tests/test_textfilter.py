from uiutils.textfilter import cycle_neighbors, filter_by_search_query


def test_filter_by_search_query_ands_terms():
    items = ["runs/multi_darcy/log.txt", "runs/mock_darcy/log.txt", "runs/solo/log.txt"]
    assert filter_by_search_query(items, "") == (items, False)
    assert filter_by_search_query(items, "darcy")[0] == items[:2]
    assert filter_by_search_query(items, "darcy multi")[0] == items[:1]  # AND, order-independent
    assert filter_by_search_query(items, "DARCY")[0] == items[:2]        # case-insensitive


def test_filter_by_search_query_bad_regex_is_reported_not_raised():
    assert filter_by_search_query(["a"], "[") == ([], True)


def test_cycle_neighbors_wraps_and_handles_stale_selection():
    items = ["a", "b", "c"]
    assert cycle_neighbors(items, "a") == ("c", "b")   # wraps backwards
    assert cycle_neighbors(items, "c") == ("b", "a")   # wraps forwards
    assert cycle_neighbors(items, "zz") == ("a", "a")  # stale selection resets
    assert cycle_neighbors([], "a") == (None, None)
