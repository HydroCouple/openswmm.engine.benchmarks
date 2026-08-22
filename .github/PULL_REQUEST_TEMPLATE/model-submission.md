## Model submission

<!-- What is this model, and what makes it worth testing every engine against? -->

### Checklist

- [ ] Case lives in `corpus/contributed/<case-id>/` with `model.inp`,
      `metadata.yaml`, and `provenance.yaml`
- [ ] `python -m harness.validate corpus/contributed/<case-id>` passes locally
- [ ] Tags chosen from `harness/schemas/tags.yaml` (new tags added in this PR,
      one line each, with a description)
- [ ] `reference.class` reflects what this model can actually prove
      (`self_consistency` is the normal answer for a real network)
- [ ] Model runs to completion on a public SWMM engine
- [ ] License declared in `provenance.yaml` and I have the right to share it
- [ ] No sensitive data — or anonymized via `harness/anonymize.py` and
      **reviewed by me** (the tool provides a layer of protection, not a
      guarantee), with the transforms recorded in `provenance.yaml`
- [ ] No absolute paths; referenced data files resolve relative to the case

### Reference

<!-- If the case carries reference data, say what it is and where it came
     from. If it doesn't, say so — that's expected. -->

### Runtime

<!-- Roughly how long does it take? Submissions land in the nightly tier;
     fast cases may be promoted to the PR tier by a maintainer. -->
