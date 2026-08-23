#!/usr/bin/env python3
"""Engine registry resolution — engines are data, not code.

Every engine the platform can benchmark is declared in ``engines.yaml``; this
module turns a declaration into a runnable executable. Three spec types:

  in-tree          an executable in a local build tree (the engine under test)
  git-ref          built from a ref of a source repo, cached per (sha, OS)
  external-binary  any SWMM-compatible CLI on PATH or at a given path

External engines are REPORT-ONLY by policy (never gating) and are excluded
from cross-engine performance claims unless declared ``comparable_build: true``
— an engine built with unknown flags is neither numerically nor performance-
comparable (BENCHMARK_REGRESSION_CI_PLAN_2026-08-16, comparable-configuration
invariant).

All executables share the SWMM CLI convention:  ``exe input.inp out.rpt out.out``

Environment overrides (CI sets these explicitly; defaults suit a local checkout):
  OPENSWMM_ENGINE_DIR      engine repo / install root
  OPENSWMM_BUILD_DIR       build tree containing bin/Release
  OPENSWMM_EXE             refactored CLI
  OPENSWMM_LEGACY_EXE      legacy CLI
  OPENSWMM_BENCH_CACHE     build cache for git-ref engines
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = Path(__file__).resolve().parent / "engines.yaml"

ENGINE_DIR = Path(os.environ.get(
    "OPENSWMM_ENGINE_DIR",
    str(REPO_ROOT.parent / "openswmm.engine")))
BUILD_DIR = Path(os.environ.get("OPENSWMM_BUILD_DIR",
                                str(ENGINE_DIR / "build" / "darwin-parity")))
BIN = BUILD_DIR / "bin" / "Release"
CACHE_DIR = Path(os.environ.get("OPENSWMM_BENCH_CACHE",
                                str(REPO_ROOT / ".engine-cache")))


# ── environment ────────────────────────────────────────────────────────────
def _dylib_dirs(build_dir: Path) -> list[str]:
    return [str(build_dir / "bin" / "Release"),
            str(build_dir / "src" / "engine"),
            str(build_dir / "src" / "legacy" / "engine"),
            str(build_dir / "src" / "legacy" / "output")]


DYLIB_DIRS = _dylib_dirs(BUILD_DIR)


def env(threads: int = 1, dylib_dirs: list[str] | None = None) -> dict:
    """Deterministic subprocess environment for engine runs."""
    e = os.environ.copy()
    paths = ":".join(dylib_dirs if dylib_dirs is not None else DYLIB_DIRS)
    for var in ("DYLD_LIBRARY_PATH", "LD_LIBRARY_PATH"):
        existing = e.get(var, "")
        e[var] = f"{paths}:{existing}" if existing else paths
    e["OMP_NUM_THREADS"] = str(threads)
    e.setdefault("OPENSWMM_2D_BACKEND", "cpu")
    return e


def available(exe: Path | None) -> bool:
    return bool(exe) and Path(exe).exists() and os.access(exe, os.X_OK)


def git_sha(repo: Path) -> str:
    """Short git SHA of a checkout, suffixed '-dirty' if the tree is modified.

    Results are published keyed by this string, so it has to describe the
    BUILD, not merely the branch tip. A checkout with uncommitted changes
    produces a binary that no commit describes; reporting the bare SHA would
    attribute those results to a commit that cannot reproduce them. This is not
    hypothetical — the engine tree carried uncommitted work throughout the
    first real sweep, and a concurrent commit moved HEAD mid-run.
    """
    try:
        sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=30).stdout.strip()
        if not sha:
            return ""
        dirty = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"],
            capture_output=True, text=True, timeout=60).stdout.strip()
        return f"{sha}-dirty" if dirty else sha
    except Exception:
        return ""


def engine_sha() -> str:
    return git_sha(ENGINE_DIR)


# ── registry model ─────────────────────────────────────────────────────────
@dataclass
class Engine:
    """One resolved entry of the engine registry."""

    id: str
    spec: dict
    out_dialect: str = "swmm53"
    gating_allowed: bool = True
    comparable_build: bool = True
    exe: Path | None = None
    status: str = "UNRESOLVED"       # RESOLVED | UNAVAILABLE | UNRESOLVED
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "RESOLVED"


@dataclass
class Comparison:
    """One pairwise comparison declared in the registry."""

    a: str
    b: str
    rtol: float = 1e-9
    atol: float = 1e-12
    gate: str = "report"             # "fail" | "report"
    note: str = ""


@dataclass
class Registry:
    engines: dict[str, Engine] = field(default_factory=dict)
    comparisons: list[Comparison] = field(default_factory=list)

    def resolved(self) -> dict[str, Engine]:
        return {k: e for k, e in self.engines.items() if e.ok}

    def active_comparisons(self) -> list[Comparison]:
        """Comparisons whose BOTH engines resolved."""
        ok = self.resolved()
        return [c for c in self.comparisons if c.a in ok and c.b in ok]


def load(path: Path | None = None) -> Registry:
    """Parse engines.yaml into a Registry (engines not yet resolved)."""
    import yaml
    path = Path(path or REGISTRY_PATH)
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    reg = Registry()
    for eid, spec in (doc.get("engines") or {}).items():
        spec = spec or {}
        source = spec.get("source", {}) or {}
        external = source.get("type") == "external-binary"
        reg.engines[eid] = Engine(
            id=eid,
            spec=spec,
            out_dialect=spec.get("out_dialect", "swmm53"),
            # policy: external engines are never gating
            gating_allowed=not external,
            comparable_build=bool(spec.get("comparable_build", not external)),
        )
    for c in (doc.get("comparisons") or []):
        reg.comparisons.append(Comparison(
            a=c["a"], b=c["b"],
            rtol=float(c.get("rtol", 1e-9)),
            atol=float(c.get("atol", 1e-12)),
            gate=c.get("gate", "report"),
            note=c.get("note", "")))
    # enforce the never-gate policy for external engines
    for c in reg.comparisons:
        for eid in (c.a, c.b):
            e = reg.engines.get(eid)
            if e and not e.gating_allowed and c.gate == "fail":
                c.gate = "report"
                c.note = (c.note + " ").strip() + \
                    f"[gate downgraded: {eid} is an external engine]"
    return reg


# ── resolution ─────────────────────────────────────────────────────────────
def resolve(engine: Engine) -> Engine:
    """Locate or build an engine's executable; set status/exe in place."""
    source = engine.spec.get("source", {}) or {}
    kind = source.get("type", "in-tree")
    try:
        if kind == "in-tree":
            engine.exe = _resolve_in_tree(source)
        elif kind == "external-binary":
            engine.exe = _resolve_external(source)
        elif kind == "git-ref":
            engine.exe = _resolve_git_ref(source)
        else:
            engine.status, engine.note = "UNAVAILABLE", f"unknown source type {kind!r}"
            return engine
    except Exception as exc:                      # never crash a sweep
        engine.status, engine.note = "UNAVAILABLE", f"{type(exc).__name__}: {exc}"
        return engine
    if available(engine.exe):
        engine.status = "RESOLVED"
    else:
        engine.status = "UNAVAILABLE"
        engine.note = engine.note or f"not executable: {engine.exe}"
    return engine


def _resolve_in_tree(source: dict) -> Path:
    target = source.get("target", "openswmm")
    env_var = source.get("env")                   # explicit override wins
    if env_var and os.environ.get(env_var):
        return Path(os.environ[env_var])
    exe_name = target + (".exe" if platform.system() == "Windows" else "")
    for candidate in (BIN / exe_name, BUILD_DIR / "bin" / exe_name,
                      BUILD_DIR / exe_name):
        if candidate.exists():
            return candidate
    return BIN / exe_name


def _resolve_external(source: dict) -> Path | None:
    env_var = source.get("env")
    if env_var and os.environ.get(env_var):
        return Path(os.environ[env_var])
    if source.get("path"):
        return Path(os.path.expandvars(str(source["path"]))).expanduser()
    if source.get("command"):
        found = shutil.which(str(source["command"]))
        return Path(found) if found else None
    return None


def _resolve_git_ref(source: dict) -> Path | None:
    """Build an engine from a git ref, cached per (ref sha, OS).

    STUB — see plan step 4 and ENGINE_524_BUILD_MODERNIZATION_PLAN. Until the
    5.2.4 branch builds multiplatform, a cached artifact is used when present
    and the engine degrades to UNAVAILABLE otherwise (never a crash).
    """
    ref = source.get("ref", "")
    target = source.get("target", "runswmm")
    exe_name = target + (".exe" if platform.system() == "Windows" else "")
    cached = CACHE_DIR / f"{ref}-{platform.system().lower()}" / exe_name
    return cached if cached.exists() else None


# ── convenience names for the two in-tree engines ──────────────────────────
# The analytical suites (swashes, transitions) were written against a
# pre-registry engines module and address the two in-tree engines directly.
# Rather than duplicate resolution logic in each suite, expose them here as
# registry-derived attributes so the registry stays the single source of
# truth. Resolved lazily (PEP 562) so importing this module costs nothing and
# so a caller that sets OPENSWMM_EXE after import still sees it.

#: Registry ids of the engine under test and its legacy reference.
REFACT_ENGINE_ID = "openswmm-v6"
LEGACY_ENGINE_ID = "swmm-5.3.0"


def exe_for(engine_id: str) -> Path | None:
    """Executable path for a registry engine id (may not exist; see available())."""
    reg = load()
    engine = reg.engines.get(engine_id)
    if engine is None:
        raise KeyError(f"no engine {engine_id!r} in {REGISTRY_PATH}")
    return resolve(engine).exe


def __getattr__(name: str):
    if name == "REFACT_EXE":
        return exe_for(REFACT_ENGINE_ID)
    if name == "LEGACY_EXE":
        return exe_for(LEGACY_ENGINE_ID)
    if name == "ENGINE":
        return REFACT_ENGINE_ID
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def resolve_all(reg: Registry, only: list[str] | None = None) -> Registry:
    """Resolve every engine (or the subset named in `only`) in place."""
    for eid, engine in reg.engines.items():
        if only and eid not in only:
            engine.status, engine.note = "UNAVAILABLE", "not selected"
            continue
        resolve(engine)
    return reg


if __name__ == "__main__":
    from . import use_utf8_stdio
    use_utf8_stdio()
    reg = resolve_all(load())
    for eid, e in reg.engines.items():
        print(f"{eid:20s} {e.status:12s} dialect={e.out_dialect:8s} "
              f"{e.exe or ''} {e.note}")
    print("\ncomparisons (both engines resolved):")
    for c in reg.active_comparisons():
        print(f"  {c.a} vs {c.b}  rtol={c.rtol} atol={c.atol} gate={c.gate}")
