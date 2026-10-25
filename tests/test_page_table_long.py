import pandas as pd
from uiutils.json_table import json_long
from uiutils.streamlit.page_table_long import add_ratio, add_split, aggregate, normalize_by_colour


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



def test_aggregate_error_bounds():
    df = pd.DataFrame({"x": ["a", "a", "a", "b"], "value": [1.0, 2.0, 6.0, 5.0]})
    plain = aggregate(df, ["x"], "value", "mean")
    assert list(plain.columns) == ["x", "value"]
    rng = aggregate(df, ["x"], "value", "median-range")
    assert rng[["value", "lo", "hi"]].to_dict("records") == [
        {"value": 2.0, "lo": 1.0, "hi": 6.0}, {"value": 5.0, "lo": 5.0, "hi": 5.0}]
    std = aggregate(df, ["x"], "value", "mean-std")
    s = df.loc[df.x == "a", "value"].std()
    assert std.loc[0, ["lo", "hi"]].tolist() == [3.0 - s, 3.0 + s]
    assert std.loc[1, ["lo", "hi"]].tolist() == [5.0, 5.0]  # single row: no spread, not NaN


def test_normalize_scales_error_bounds_with_the_centre():
    df = pd.DataFrame({"c": ["A", "A"], "v": [2.0, 4.0], "lo": [1.0, 2.0], "hi": [3.0, 8.0]})
    res = normalize_by_colour(df, "c", "v", ("lo", "hi"))
    assert res["lo"].tolist() == [0.25, 0.5]
    assert res["hi"].tolist() == [0.75, 2.0]


def test_add_split_names_groups_and_marks_non_matches():
    df = pd.DataFrame({"run": ["0Infr_a", "12infr_b", "multiB"], "value": [1.0, 2.0, 3.0]})
    assert add_split(df, "run", r"(\d+)Infr")["run_rx1"].tolist() == ["0", "12", "not-matched"]
    named = add_split(df, "run", r"(?P<seed>\d+)Infr(_(?P<tail>\w))?")
    assert named[["seed", "tail"]].to_numpy().tolist() == [["0", "a"], ["12", "b"], ["not-matched"] * 2]
    assert add_split(df, "run", "Infr")["run_rx"].tolist() == ["Infr", "infr", "not-matched"]
