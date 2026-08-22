#!/usr/bin/env python3
"""Suite registry for run_regression.py.

Nested suites are supported one level deep (``suites/analytical/swashes/``),
so families of related suites share a parent directory; a nested suite is
named ``parent/child``.

A suite is a folder ``suites/<name>/`` containing a ``suite.py`` module that
exposes:

    def run(argv: list[str]) -> dict     # executes the sweep, returns the
                                         # scores envelope (core.scoring shape)
    def report(argv: list[str]) -> list  # regenerates the suite's markdown
                                         # report + figures, returns paths

No plugin machinery: the registry is a dict built by scanning suites/ for
suite.py files and importing them by path.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SUITES_DIR = REPO_ROOT / "suites"


def _names() -> list[tuple[str, Path]]:
    found = [(p.parent.name, p) for p in sorted(SUITES_DIR.glob("*/suite.py"))]
    found += [(f"{p.parent.parent.name}/{p.parent.name}", p)
              for p in sorted(SUITES_DIR.glob("*/*/suite.py"))]
    return found


def list_suites() -> list[str]:
    """Suite names without importing them (cheap; for --list and CI)."""
    return [name for name, _ in _names()]


def discover(only: list[str] | None = None) -> dict[str, object]:
    reg: dict[str, object] = {}
    for name, suite_py in _names():
        if only and name not in only:
            continue
        mod_name = "suites." + name.replace("/", ".") + ".suite"
        spec = importlib.util.spec_from_file_location(mod_name, suite_py)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        reg[name] = mod
    return reg
