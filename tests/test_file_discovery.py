from uiutils.file_discovery import find_outputs, find_reports


def _touch(root, *rels):
    for rel in rels:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")


def test_find_outputs_skips_excluded_and_pruned_dirs(tmp_path):
    _touch(tmp_path, "a.png", "log_a.txt", ".venv/b.png", "big/c.png", "d/run.log")

    pngs, logs = find_outputs(tmp_path, prune=lambda d: d.name == "big")

    assert pngs == ["a.png"]
    assert set(logs) == {"log_a.txt", "d/run.log"}


def test_find_reports_depth_limit_and_agents_exclusion(tmp_path):
    _touch(tmp_path, "a.md", "d1/b.md", "d1/d2/c.md", "d1/d2/d3/too_deep.md", ".agents/plan.md")

    assert set(find_reports(tmp_path)) == {"a.md", "d1/b.md", "d1/d2/c.md"}
