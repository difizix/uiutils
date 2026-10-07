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
