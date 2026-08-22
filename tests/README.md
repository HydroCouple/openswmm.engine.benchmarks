# Harness tests

**These tests require no SWMM engine.** `.out` fixtures are synthesized by
`outfixture.py` and `.rpt` fixtures are inline text, so the readers, comparison
logic, tag queries, validator, and scoring policy are all verified on any
runner — including a contributor's laptop with nothing built.

```bash
pip install -r requirements.txt pytest
python -m pytest
```

| file | covers |
|---|---|
| `outfixture.py` | synthetic `.out` writer: configurable elements, pollutants, and system-variable count (both dialects) |
| `test_readers.py` | subcatchment/node/link/system series, pollutant naming, dialect derivation, malformed files |
| `test_compare.py` | pollutant + subcatchment + system coverage, cross-dialect intersection, tolerance handling, offender ranking |
| `test_rptparse.py` | continuity, stability, multi-pollutant quality continuity, LID performance, error collection |
| `test_corpus_and_validate.py` | tag expressions, metadata/provenance validation, anonymization advisories, badge and gating policy |

## Why the fixtures are synthetic

The platform's premise is that it grades engines it did not build and cannot
run. Tests that need a compiled engine could not verify that premise, and
would not run in the validation workflow that gates community submissions.
