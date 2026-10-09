from uiutils.tree import build_tree, tree_contains


def test_build_tree():
    tree = build_tree(["todox/NOW.md", "todox/plans/a.md", "todox/plans/done/b.md"], strip="todox/")
    assert tree == {"NOW.md": "todox/NOW.md",
                    "plans/": {"a.md": "todox/plans/a.md", "done/": {"b.md": "todox/plans/done/b.md"}}}
    assert tree_contains(tree["plans/"], "todox/plans/done/b.md")
    assert not tree_contains(tree["plans/"], "todox/NOW.md")
