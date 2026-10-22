#!/usr/bin/env python3
"""Dispatch submitted cases to their owning suite, preserving its gate status."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from harness import corpus, scoring


def partition(ids):
    cases={c.id:c for c in corpus.load()}
    missing=set(ids)-cases.keys()
    if missing:raise ValueError('Unknown submitted cases: '+','.join(sorted(missing)))
    uk=[ident for ident in ids if 'uk_ea_2d' in cases[ident].tags]
    return [ident for ident in ids if ident not in uk],uk


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--only',required=True);ap.add_argument('--max-wall',type=float,default=300)
    args=ap.parse_args(argv)
    generic,uk=partition(args.only.split(','));rc=0
    records={c.id:c for c in corpus.load()}
    river=[ident for ident in generic if 'uk_ea_river' in records[ident].tags]
    generic=[ident for ident in generic if ident not in river]
    if generic:
        from suites.parity import suite
        env=suite.run(['--tier','nightly','--only',','.join(generic),'--max-wall',str(args.max_wall),'--keep-out','none'])
        rc|=scoring.exit_code(env)
    if uk:
        from suites.uk_2d import suite
        opts=['--tier','nightly','--only',','.join(uk),'--max-wall',str(args.max_wall)]
        env=suite.run(opts);suite.report(opts);rc|=scoring.exit_code(env)
    if river:
        from suites.uk_river import suite
        opts=['--only',','.join(ident.removeprefix('uk-river-') for ident in river),'--max-wall',str(args.max_wall)]
        env=suite.run(opts);suite.report(opts);rc|=scoring.exit_code(env)
    if not generic and not uk and not river:return 1
    return rc

if __name__=='__main__':sys.exit(main())
