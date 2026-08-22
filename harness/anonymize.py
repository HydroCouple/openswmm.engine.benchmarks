#!/usr/bin/env python3
"""Best-effort anonymization of a SWMM model — STUB.

**No tool can guarantee anonymity, and this one does not claim to.** It
provides a LAYER of anonymization that, combined with the submitter's own
review, can make an otherwise unshareable model shareable. Final
responsibility for data sensitivity rests with the submitter.

Planned transforms (each individually selectable):
  * rename subcatchment / node / link / gage / curve / pattern / LID IDs via a
    consistent map, emitted to a side file the submitter keeps privately
  * offset or rotate coordinates to a neutral origin, or strip
    [COORDINATES] / [VERTICES] / [POLYGONS] / [MAP] entirely
  * scrub free text: [TITLE], ';' comments, [TAGS], rain-gage station IDs,
    absolute file paths
  * rename and relocate external forcing files under data/

Correctness invariant (enforced by --verify): the model is run before and
after and the resulting .out must be BIT-IDENTICAL. Anonymization must never
change physics.

Design detail lives in plans/MODEL_ANONYMIZATION_STRATEGY.md (to be written);
this module lands with the submission pathway (plan step 5).

Intended CLI:
    python -m harness.anonymize model.inp -o anon.inp --map ids.json \\
        --coords offset --scrub-text --verify --engine openswmm-v6
"""
from __future__ import annotations

import argparse
import sys

TRANSFORMS = ("rename-ids", "coords-offset", "coords-strip", "scrub-text",
              "relocate-data")


def anonymize(*_args, **_kwargs):
    raise NotImplementedError(
        "harness.anonymize is a scaffold stub — see "
        "plans/BENCHMARK_PLATFORM_PLAN_2026-08-22.md (Model anonymization) "
        "and plan step 5.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inp", nargs="?", help="model to anonymize")
    ap.add_argument("-o", "--out", help="output model path")
    ap.add_argument("--transforms", default=",".join(TRANSFORMS))
    ap.add_argument("--verify", action="store_true",
                    help="run before/after and require bit-identical .out")
    ap.parse_args(argv)
    print(__doc__, file=sys.stderr)
    print("NOT IMPLEMENTED — scaffold stub.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
