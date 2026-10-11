from uiutils.makefile_targets import parse_makefile

MAKEFILE = """\
RUN?=multiB
DMOG_DIR ?= /scratch/${USER}/difiz
CACHE := out/$(RUN)

# Build the study:
# both caches.
.PHONY: study
study:
\tpython a.py --run $(RUN) \\
\t    --refresh
\t@echo done

down:   # stop, keep volumes
\tdocker compose down

%.o: %.c
\tcc $<
"""


def test_parse_makefile(tmp_path):
    mk = tmp_path / "Makefile"
    mk.write_text(MAKEFILE)
    targets, variables = parse_makefile(mk)

    assert variables == {"RUN": "multiB", "DMOG_DIR": "/scratch/${USER}/difiz"}
    assert [t.name for t in targets] == ["study", "down"]
    study, down = targets
    assert study.doc == "Build the study:\nboth caches."
    assert study.recipe == ["python a.py --run $(RUN) --refresh", "@echo done"]
    assert down.doc == "stop, keep volumes"
    assert down.recipe == ["docker compose down"]


def test_parse_makefile_include(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "deps.mk").write_text("GIT ?= https://x\nRUN ?= other\n\ndeps:  # install deps\n\tgit clone $(GIT)\n")
    mk = tmp_path / "Makefile"
    mk.write_text("RUN ?= a\ninclude sub/deps.mk\n-include missing.mk $(X)\n\nall:\n\techo\n")
    targets, variables = parse_makefile(mk)

    assert [t.name for t in targets] == ["deps", "all"]
    assert targets[0].doc == "install deps"
    assert variables == {"RUN": "a", "GIT": "https://x"}  # the first ?= wins, as in make
