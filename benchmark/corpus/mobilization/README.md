# Mobilization labelled set

Issue #34.

This set measures two things about mobilization confirmation:

1. **Detection precision**, weighted over recall.
   A false mobilization alert about a political group is the worst output
   this system can produce, and the lexicon already catches the obvious
   cases, so lower recall is tolerable and lower precision is not.
2. **Date and place exact-match accuracy** on the examples that do contain a
   call to assemble.

## The set is not shipped populated

`labelled.yaml` currently holds a small worked example set, marked
`provenance: synthetic`. It exercises the harness. It does **not** satisfy
the issue's requirement, and running the benchmark against it proves
nothing about production behaviour.

The acceptance bars in #34 are measured on **100 to 200 examples drawn from
public reporting of past events**. Assembling that set is human work and
deliberately not automated: examples invented by a model would measure the
model against its own priors.

Until the real set exists, `MOBILIZATION_CONFIRM_ENABLED` stays `false` and
the lexicon runs alone, which still produces a defensible signal. The issue
records that as a planned outcome rather than a failure.

## Collecting the real set

Each entry needs:

- `text`: the content as published, in its original language
- `language`: `en` or `hi`
- `is_call_to_assemble`: whether it actually calls for people to gather
- `expected_date`: ISO date the content states, or `null`
- `expected_place`: the place the content states, or `null`
- `source_url`: where it was published, so a reviewer can check the label
- `provenance: public_reporting`

Aim for roughly a third negatives, and include the hard negatives
deliberately: reports *about* a past gathering, announcements of a meeting
between officials, and calls to sign a petition rather than to assemble.
Those are where a confirmation model earns or loses its precision.

Relative and colloquial date expressions are the hard part, and they may
extract better from translated text than from the original. Label both and
let the benchmark say which.

## Running it

    uv run python -m benchmark.mobilization --set benchmark/corpus/mobilization/labelled.yaml

Add `--compare-cloud` to measure the cloud model on the same set. That
requires `LLM_CLOUD_ENABLED=true`, which is refused outside a development
environment. See ADR 0002.
