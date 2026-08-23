"""The analytical layer, verified without an engine.

These are the platform's only accuracy claims, so the reference data behind
them has to be trustworthy independently of any build. Each committed
``reference.csv`` should still be exactly reproducible from the closed-form
solution its provenance documents — if a formula, a constant, or a unit
conversion drifts, the reference stops matching and that must be visible
before anyone grades an engine against it.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MANUFACTURED = REPO_ROOT / "suites" / "analytical" / "manufactured" / "cases"
SWASHES = REPO_ROOT / "suites" / "analytical" / "swashes" / "cases"
TRANSITIONS = REPO_ROOT / "suites" / "analytical" / "transitions" / "cases"


def _generator_cases() -> list[Path]:
    if not MANUFACTURED.is_dir():
        return []
    return [d for d in sorted(MANUFACTURED.iterdir())
            if (d / "scripts").is_dir() and list((d / "scripts").glob("*.py"))]


@pytest.mark.parametrize("case", _generator_cases(),
                         ids=lambda c: c.name)
def test_manufactured_reference_is_reproducible(case, tmp_path):
    """The generator must still produce the committed reference byte for byte."""
    ref = case / "reference.csv"
    before = ref.read_bytes()
    script = sorted((case / "scripts").glob("*.py"))[0]
    try:
        proc = subprocess.run([sys.executable, str(script)], cwd=str(case),
                              capture_output=True, text=True, timeout=300)
        assert proc.returncode == 0, proc.stderr[-400:]
        assert ref.read_bytes() == before, (
            f"{case.name}: the generator no longer reproduces reference.csv")
    finally:
        ref.write_bytes(before)          # never leave committed data modified


def test_every_analytical_case_has_provenance():
    """An analytic reference without provenance is an unsourced assertion."""
    missing = []
    for root in (MANUFACTURED, SWASHES, TRANSITIONS):
        if not root.is_dir():
            continue
        for case in sorted(root.iterdir()):
            if case.is_dir() and not (case / "provenance.yaml").exists():
                missing.append(f"{root.name}/{case.name}")
    assert not missing, f"cases without provenance.yaml: {missing}"


def test_reference_class_is_a_truth_class():
    """Everything under analytical/ must be gradeable as an accuracy claim.

    This is what separates the verification badge from the regression badge;
    if a suite here declared a non-truth reference class, error norms computed
    from it would be meaningless.
    """
    from harness import scoring
    sys.path.insert(0, str(REPO_ROOT))
    for name in ("swashes", "transitions", "manufactured"):
        mod_path = REPO_ROOT / "suites" / "analytical" / name / "suite.py"
        if not mod_path.exists():
            continue
        text = mod_path.read_text()
        assert 'REFERENCE_CLASS = "' in text, f"{name}: no REFERENCE_CLASS declared"
        cls = text.split('REFERENCE_CLASS = "')[1].split('"')[0]
        assert scoring.is_truth(cls), (
            f"{name} declares reference class {cls!r}, which is not ground "
            "truth — accuracy metrics from it would be unsupportable")


@pytest.mark.skipif(not SWASHES.is_dir(), reason="swashes suite not migrated")
def test_swashes_cases_carry_reference_data():
    empty = [c.name for c in sorted(SWASHES.iterdir())
             if c.is_dir() and not (c / "reference.csv").exists()]
    # the bend cases use engine-generated 2D references, not closed-form ones
    unexpected = [c for c in empty if not c.startswith("bend")]
    assert not unexpected, f"cases missing reference.csv: {unexpected}"


def test_every_yaml_in_the_repository_parses():
    """One unparseable YAML file breaks every consumer at once.

    Three shipped broken during this work: a tag description beginning with
    "[" (read as a flow sequence), a provenance description beginning with "|"
    (absolute-value notation read as a block scalar), and a list item
    containing a colon. None of them failed loudly at the point of authorship
    — they failed later, in whatever tool happened to load the file first.
    """
    import yaml

    bad = []
    for p in sorted(REPO_ROOT.rglob("*.yaml")):
        if ".git" in p.parts or "legacy" in p.parts:
            continue
        try:
            yaml.safe_load(p.read_text())
        except yaml.YAMLError as exc:
            bad.append(f"{p.relative_to(REPO_ROOT)}: "
                       f"{str(exc).splitlines()[0]}")
    assert not bad, "unparseable YAML:\n  " + "\n  ".join(bad)


def test_every_analytical_provenance_is_a_mapping():
    """Provenance must be structured data, not an accidental string."""
    import yaml

    for root in (MANUFACTURED, SWASHES, TRANSITIONS):
        if not root.is_dir():
            continue
        for case in sorted(root.iterdir()):
            prov = case / "provenance.yaml"
            if not prov.exists():
                continue
            doc = yaml.safe_load(prov.read_text())
            assert isinstance(doc, dict), f"{case.name}: provenance is not a mapping"


def test_generators_declare_an_output_encoding():
    """A generator that writes non-ASCII must not depend on the locale.

    reference.csv headers carry '≈', '—', '²'. `open(..., "w")` without an
    encoding uses the platform default, which is cp1252 on a Windows runner —
    so the generator dies with UnicodeEncodeError before writing a byte, and
    the byte-exactness test above reports the unmet claim rather than the real
    cause. The committed references are UTF-8; saying so explicitly reproduces
    them identically everywhere.
    """
    import re
    offenders = []
    for script in sorted(MANUFACTURED.glob("*/scripts/*.py")):
        for call in re.findall(r'open\([^()]*"w"[^()]*\)', script.read_text(encoding="utf-8")):
            if "encoding=" not in call:
                offenders.append(f"{script.parent.parent.name}: {call}")
    assert not offenders, "writes without an explicit encoding:\n  " + "\n  ".join(offenders)
