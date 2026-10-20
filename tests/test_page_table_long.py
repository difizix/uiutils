import pandas as pd
from uiutils.json_table import json_long
from uiutils.streamlit.page_table_long import add_ratio, normalize_by_colour


def test_json_long_keeps_numeric_leaves_with_their_paths():
    assert json_long({"run": {"tags": ["a"], "std": {"g1": {"sw": 0.5}}, "std_all": {"sw": 0.4}, "ok": True}}) == [
        {"level0": "run", "level1": "std", "level2": "g1", "level3": "sw", "value": 0.5},
        {"level0": "run", "level1": "std_all", "level2": "sw", "value": 0.4},
    ]


def test_add_ratio_pairs_rows_by_the_other_labels():
    df = pd.DataFrame({"geo": ["g1", "g1", "g2", "g2", "g3"], "tag": ["A", "B", "A", "B", "A"],
                       "value": [2.0, 4.0, 3.0, 0.0, 1.0]})
    ratio = add_ratio(df, "tag", "A", "B").query("tag == 'A/B'")
    # g2 divides by zero and g3 has no B: both dropped
    assert ratio[["geo", "value"]].to_dict("records") == [{"geo": "g1", "value": 0.5}]


def test_normalize_by_colour_peaks_at_one():
    df = pd.DataFrame({
        "x": ["x1", "x2", "x1", "x2", "x1", "x2"],
        "c": ["A", "A", "B", "B", "Z", "Z"],
        "v": [2.0, 4.0, 10.0, 100.0, 0.0, 0.0],
    })
    res = normalize_by_colour(df, "c", "v")
    assert res.loc[res["c"] == "A", "v"].tolist() == [0.5, 1.0]
    assert res.loc[res["c"] == "B", "v"].tolist() == [0.1, 1.0]
    # zero max remains 0.0 without crashing
    assert res.loc[res["c"] == "Z", "v"].tolist() == [0.0, 0.0]

