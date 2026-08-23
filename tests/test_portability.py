#!/usr/bin/env python3
"""Portability invariants the CI matrix depends on.

The harness job runs on Linux, macOS and Windows. Every bug these pin was found
by that matrix and was invisible on a developer machine, so they are checked
here rather than left to a runner to rediscover.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = ("harness", "tools", "tests", "suites")

#: Modes that are byte-oriented; an encoding is meaningless (and an error) there.
_BINARY_MODES = ("b",)


def _python_files() -> list[Path]:
    files: list[Path] = [REPO_ROOT / "run_regression.py"]
    for root in SOURCE_ROOTS:
        files += sorted((REPO_ROOT / root).rglob("*.py"))
    return [f for f in files if f.is_file()]


def _text_io_without_encoding(path: Path) -> list[str]:
    """read_text/write_text/open calls in `path` that don't declare an encoding."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:                       # not ours to police
        return []
    bad = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            name = node.func.attr
        elif isinstance(node.func, ast.Name):
            name = node.func.id
        else:
            continue
        if name not in ("read_text", "write_text", "open"):
            continue
        if any(kw.arg == "encoding" for kw in node.keywords):
            continue
        if name == "open":
            mode = ""
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                mode = str(node.args[1].value)
            for kw in node.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = str(kw.value.value)
            if any(b in mode for b in _BINARY_MODES):
                continue
        bad.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}: {name}()")
    return bad


def test_all_text_io_declares_an_encoding():
    """Text IO must not inherit the platform's locale encoding.

    Without `encoding=`, Python uses the locale default: UTF-8 on the Linux and
    macOS runners, cp1252 on Windows. Reading UTF-8 corpus metadata as cp1252
    does not raise -- cp1252 maps every byte -- it silently yields mojibake,
    which is worse than a crash. Writing is worse still: the dashboard pages
    declare `<meta charset=utf-8>`, so a cp1252 write produces a file that lies
    about its own encoding. Every text path in this repository is UTF-8; the
    code has to say so.
    """
    offenders = [o for f in _python_files() for o in _text_io_without_encoding(f)]
    assert not offenders, (
        "text IO without an explicit encoding:\n  " + "\n  ".join(offenders))


@pytest.mark.parametrize("path, expected", [
    ("/etc/passwd", True),
    ("C:\\Users\\someone\\model.inp", True),
    ("D:/data/ref.csv", True),
    ("\\\\server\\share\\ref.csv", True),
    ("reference/legacy.rpt", False),
    ("./ref.csv", False),
    ("a/b/c.dat", False),
])
def test_absolute_path_detection_is_os_independent(path, expected):
    """`Path.is_absolute()` answers for the host; the corpus is shared.

    On Linux a `C:\\...` path reads as relative and on Windows a `/etc/...` one
    does, so a single-flavour check passes exactly the paths the other platform
    cares about.
    """
    from harness import validate
    assert validate.is_absolute_anywhere(path) is expected
