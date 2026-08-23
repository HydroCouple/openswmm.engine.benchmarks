"""Tag queries, corpus selection, metadata validation, and scoring policy."""
from __future__ import annotations

import shutil

import pytest

from harness import corpus, scoring, validate

TAGS = {"lid", "pollutants", "hydraulics", "real_world"}


@pytest.mark.parametrize("expr,want", [
    ("lid", True),
    ("performance", False),
    ("lid AND pollutants", True),
    ("lid AND performance", False),
    ("lid OR performance", True),
    ("NOT performance", True),
    ("NOT lid", False),
    ("lid pollutants", True),                       # adjacency means AND
    ("(hydraulics OR hydrology) AND real_world", True),
    ("(hydraulics OR hydrology) AND regression", False),
    ("transient AND NOT performance", False),
    ("NOT (lid AND performance)", True),
    ("lid and pollutants", True),                   # operators are case-insensitive
])
def test_tag_expressions(expr, want):
    assert corpus.matches(TAGS, expr) is want


@pytest.mark.parametrize("expr", [
    "lid AND pollutants\n",                        # YAML `select: >` folded scalar
    "  lid AND pollutants  ",
    "lid AND pollutants\n\n",
])
def test_tag_expressions_tolerate_surrounding_whitespace(expr):
    """Manifests write queries as YAML folded scalars, which always end with a
    newline. Rejecting that would break every manifest."""
    assert corpus.matches(TAGS, expr) is True


@pytest.mark.parametrize("expr", ["lid AND", "(lid", "lid )", "", "AND lid"])
def test_malformed_tag_expressions_are_rejected(expr):
    """A typo in a manifest must fail loudly — silently selecting nothing would
    look like a green run over an empty corpus."""
    with pytest.raises(ValueError):
        corpus.matches(TAGS, expr)


def test_tag_vocabulary_parses_and_is_wellformed():
    """A tags.yaml that does not parse fails every validation at once.

    It broke once because a description beginning with "[" was read as a YAML
    flow sequence — descriptions are prose and must be quoted when they start
    with a structural character.
    """
    import yaml
    doc = yaml.safe_load(
        (validate.SCHEMA_DIR / "tags.yaml").read_text())
    tags = doc["tags"]
    assert len(tags) > 40
    for name, desc in tags.items():
        assert isinstance(name, str) and name == name.lower(), name
        assert isinstance(desc, str) and desc.strip(), f"{name}: bad description"


def test_finite_volume_solvers_are_in_the_vocabulary():
    """The engine implements 1D FV (FLOW_ROUTING FV) and 2D shallow-water FV;
    both are benchmarked by the swashes solver matrix, so both need tags."""
    vocab = validate.load_tags()
    assert "finite_volume" in vocab
    assert "finite_volume_2d" in vocab
    assert "FV" in validate.VALID_ROUTING


def _make_case(root, case_id="smoke-case", **overrides):
    """A minimal valid case built from the shipped template."""
    import yaml
    src = validate.REPO_ROOT / "corpus" / "_template"
    dst = root / "corpus" / "contributed" / case_id
    dst.mkdir(parents=True)
    for name in ("metadata.yaml", "provenance.yaml"):
        shutil.copy(src / name, dst / name)
    (dst / "model.inp").write_text("[TITLE]\ntest\n")
    meta = yaml.safe_load((dst / "metadata.yaml").read_text())
    meta["id"] = case_id
    meta.update(overrides)
    (dst / "metadata.yaml").write_text(yaml.safe_dump(meta))
    return dst


def test_shipped_template_is_valid(tmp_path):
    """The template contributors copy must itself pass validation."""
    r = validate.validate_case(_make_case(tmp_path))
    assert r.ok, r.errors
    assert r.warnings == []


def test_unknown_tag_is_rejected(tmp_path):
    case = _make_case(tmp_path, tags=["hydraulics", "not_a_real_tag"])
    r = validate.validate_case(case)
    assert not r.ok
    assert any("not_a_real_tag" in e for e in r.errors)


def test_unknown_reference_class_is_rejected(tmp_path):
    case = _make_case(tmp_path, reference={"class": "vibes"})
    r = validate.validate_case(case)
    assert any("reference.class" in e for e in r.errors)


def test_blessed_baseline_requires_its_review_record(tmp_path):
    """A pinned baseline is only as good as the review that pinned it."""
    case = _make_case(tmp_path, reference={"class": "blessed_baseline"})
    r = validate.validate_case(case)
    missing = {e.split(".")[2].split(" ")[0] for e in r.errors
               if "blessed_by" in e}
    assert missing == {"engine", "sha", "reviewer", "date"}


def test_blessed_baseline_with_full_record_passes(tmp_path):
    case = _make_case(tmp_path, reference={
        "class": "blessed_baseline",
        "blessed_by": {"engine": "openswmm-v6", "sha": "abc1234",
                       "reviewer": "C. Buahin", "date": "2026-08-22"}})
    assert validate.validate_case(case).ok


def test_missing_model_file_is_rejected(tmp_path):
    case = _make_case(tmp_path)
    (case / "model.inp").unlink()
    r = validate.validate_case(case)
    assert any("model file not found" in e for e in r.errors)


def test_missing_reference_file_is_rejected(tmp_path):
    case = _make_case(tmp_path, reference={
        "class": "external_reference", "source": "swmm4_dat",
        "files": ["reference/absent_q.dat"]})
    r = validate.validate_case(case)
    assert any("reference file not found" in e for e in r.errors)


@pytest.mark.parametrize("path", [
    "/etc/passwd",                 # POSIX absolute
    "C:\\secrets\\creds.dat",        # Windows drive, backslash
    "D:/data/ref.csv",             # Windows drive, forward slash
    "\\\\server\\share\\ref.csv",     # UNC
])
def test_absolute_reference_path_is_rejected(tmp_path, path):
    """Rejection must not depend on which OS is running the validator.

    `Path.is_absolute()` answers for the host, so on Linux a `C:\\...` path reads
    as relative and on Windows a `/etc/...` path does — each platform waving
    through exactly the paths the other cares about. The corpus is shared and
    full of Windows paths authored elsewhere, so both flavours are checked.
    """
    case = _make_case(tmp_path, reference={
        "class": "external_reference", "files": [path]})
    r = validate.validate_case(case)
    assert any("relative path" in e for e in r.errors), r.errors


@pytest.mark.parametrize("path", [
    "reference/legacy.rpt", "./ref.csv", "a/b/c.dat", "ref.csv",
])
def test_relative_reference_paths_are_accepted(path, tmp_path):
    """The check must not become so eager it rejects ordinary relative paths."""
    assert not validate.is_absolute_anywhere(path)


def test_inp_scan_flags_latlong_coordinates(tmp_path):
    """Advisory, not fatal: coordinates that look like real-world lat/long are
    surfaced so the submitter can decide, since anonymization is never
    automatic and never guaranteed."""
    case = _make_case(tmp_path)
    (case / "model.inp").write_text(
        "[COORDINATES]\nN1  -111.891050  40.760780\nN2  -111.892000  40.761000\n")
    r = validate.validate_case(case)
    assert r.ok                                    # advisory only
    assert any("lat/long" in w for w in r.warnings)


@pytest.mark.parametrize("line", [
    "USE RAINFALL /Users/someone/rain.dat",        # posix, mid-line after keyword
    "SAVE HOTSTART C:\\TEMP\\HS.HSF",              # windows drive letter
    "USE RAINFALL D:/IM/Projects/gauge.dat",       # drive letter, forward slashes
    "; model from /home/analyst/work/model.inp",   # in a comment
])
def test_inp_scan_flags_absolute_paths(tmp_path, line):
    """Absolute paths break the moment a model runs on another machine, and
    they routinely leak usernames and project names."""
    case = _make_case(tmp_path)
    (case / "model.inp").write_text(f"[FILES]\n{line}\n")
    r = validate.validate_case(case)
    assert any("absolute path" in w for w in r.warnings), r.warnings


def test_inp_scan_does_not_flag_urls(tmp_path):
    """'https://' must not read as a drive letter — a URL in a comment is
    normal and flagging it would train contributors to ignore the warnings."""
    case = _make_case(tmp_path)
    (case / "model.inp").write_text(
        "[TITLE]\n; see https://www.openswmm.org/Thread/9869/comparison\n")
    r = validate.validate_case(case)
    assert not any("absolute path" in w for w in r.warnings), r.warnings


# ── scoring policy ─────────────────────────────────────────────────────────

def test_only_truth_classes_permit_accuracy_metrics():
    assert scoring.is_truth("analytic")
    assert scoring.is_truth("manufactured")
    for cls in ("external_reference", "observed", "blessed_baseline",
                "self_consistency"):
        assert not scoring.is_truth(cls)
        with pytest.raises(ValueError):
            scoring.check_accuracy_allowed(cls)
    scoring.check_accuracy_allowed("analytic")      # must not raise


def test_verification_badge_counts_only_truth_cases():
    """The whole point of the split: a large corpus passing regression must
    never be presented as an accuracy claim."""
    env = {"suite": "t", "cells": [
        {"case": "a", "reference_class": "analytic", "verdict": "PASS"},
        {"case": "b", "reference_class": "manufactured", "verdict": "FAIL"},
        {"case": "c", "reference_class": "self_consistency", "verdict": "PASS"},
        {"case": "d", "reference_class": "self_consistency", "verdict": "PASS"},
    ]}
    badges = scoring.badges([env], corpus_count=1589)
    # "checked", not "cases": skipped work is excluded from the ratio and
    # disclosed separately (see tests/test_site.py).
    assert badges["verification"]["message"] == "1/2 checked"
    assert badges["verification"]["color"] == scoring.BADGE_RED
    assert badges["regression"]["message"] == "passing"
    assert badges["models"]["message"] == "1,589"


def test_mass_balance_badge_thresholds():
    def worst(err):
        env = {"suite": "t", "cells": [{"case": "a", "continuity_err": err}]}
        return scoring.badges([env])["mass-balance"]["color"]
    assert worst(0.4) == scoring.BADGE_GREEN
    assert worst(-3.0) == scoring.BADGE_YELLOW     # sign must not matter
    assert worst(9.0) == scoring.BADGE_RED


def test_exit_code_gates_on_failures():
    ok = {"suite": "t", "cells": [{"verdict": "PASS"}, {"verdict": "SKIP"},
                                  {"verdict": "UNAVAILABLE"}]}
    bad = {"suite": "t", "cells": [{"verdict": "PASS"}, {"verdict": "FAIL"}]}
    xpass = {"suite": "t", "cells": [{"verdict": "XPASS"}]}
    assert scoring.exit_code(ok) == 0
    assert scoring.exit_code(bad) == 1
    assert scoring.exit_code(xpass) == 1           # unexpected pass is loud


def test_envelope_cells_are_replaced_not_duplicated(tmp_path):
    """Re-running one cell must overwrite it so interrupted sweeps resume
    cleanly instead of accumulating stale verdicts."""
    env = scoring.new_envelope("t", "abc123")
    path = tmp_path / "scores.json"
    scoring.save_cell(path, env, {"case": "a", "solver": "e1", "verdict": "FAIL"})
    scoring.save_cell(path, env, {"case": "a", "solver": "e1", "verdict": "PASS"})
    scoring.save_cell(path, env, {"case": "a", "solver": "e2", "verdict": "PASS"})
    assert len(env["cells"]) == 2
    assert scoring.exit_code(env) == 0
    assert scoring.load(path)["cells"] == env["cells"]
