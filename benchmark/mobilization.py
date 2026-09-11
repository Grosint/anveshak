"""Mobilization confirmation benchmark — issue #34.

Measures a model against a labelled set on two bars:

  detection precision            at least 0.85
  date and place exact match     at least 0.70

Precision is weighted over recall. A false mobilization alert about a
political group is the worst output this system can produce, and the lexicon
already catches the obvious cases, so lower recall is tolerable.

Three arms can be measured on the same set and the same scorer:

  lexicon    the versioned pattern file, alone. No model, no network.
  local      the confirmation prompt against Ollama.
  cloud      the confirmation prompt against a cloud provider.

The lexicon arm is what a vocabulary change is measured against. The lexicon
ships enabled while confirmation does not, so a pattern added for recall has
to show that it did not cost precision, and that measurement must not need a
model that is switched off.

Run:

    uv run python -m benchmark.mobilization --arm lexicon \\
        --set benchmark/corpus/mobilization/labelled.yaml

Add --compare-cloud to measure a cloud model on the same set. That requires
LLM_CLOUD_ENABLED=true, which is refused outside a development environment.
See docs/adr/0002-cloud-model-guard.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Optional

import yaml

RESULTS_DIR = Path("benchmark/results")

# The labelled sets state absolute dates, so a relative expression in the
# content has to resolve against a fixed day or the recorded numbers change
# at the year boundary.
REFERENCE_TODAY = date(2026, 3, 4)


def _normalise(value: Optional[str]) -> str:
    """Compare extractions case-insensitively with whitespace collapsed.

    Exact match on the substance, not on incidental formatting.
    """
    if not value:
        return ""
    return " ".join(str(value).strip().lower().split())


def score_predictions(
    predictions: list[dict[str, Any]],
    truth: list[dict[str, Any]],
) -> dict[str, Any]:
    """Precision on detection, exact-match accuracy on date and place.

    Extraction accuracy is computed only on the true positives: a correct
    null on a non-call says nothing about extraction, and neither does a
    null the arm produced by missing the call altogether.
    """
    if len(predictions) != len(truth):
        raise ValueError(
            f"{len(predictions)} predictions against {len(truth)} labelled examples"
        )

    true_positives = 0
    false_positives = 0
    false_negatives = 0
    extraction_total = 0
    extraction_correct = 0

    for predicted, actual in zip(predictions, truth):
        said_call = bool(predicted.get("is_call_to_assemble"))
        is_call = bool(actual.get("is_call_to_assemble"))

        if said_call and is_call:
            true_positives += 1
        elif said_call and not is_call:
            false_positives += 1
        elif not said_call and is_call:
            false_negatives += 1

        # Scored only where the arm found the call. Counting a missed call
        # as a correct null extraction reads as accuracy where there was no
        # extraction at all.
        if is_call and said_call:
            extraction_total += 1
            if _normalise(predicted.get("date")) == _normalise(
                actual.get("expected_date")
            ) and _normalise(predicted.get("place")) == _normalise(
                actual.get("expected_place")
            ):
                extraction_correct += 1

    predicted_calls = true_positives + false_positives
    actual_calls = true_positives + false_negatives

    return {
        "precision": (true_positives / predicted_calls) if predicted_calls else 0.0,
        # Reported for context. It is not a bar.
        "recall": (true_positives / actual_calls) if actual_calls else 0.0,
        "date_place_accuracy": (
            extraction_correct / extraction_total if extraction_total else 0.0
        ),
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "extraction_scored": extraction_total,
        "extraction_correct": extraction_correct,
    }


def load_labelled_set(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text()) or {}
    examples = data.get("examples", [])
    if not examples:
        raise SystemExit(f"{path} contains no examples")
    return data


def predict_lexicon(
    examples: list[dict[str, Any]], *, today: Optional[date] = None
) -> list[dict[str, Any]]:
    """Run the lexicon over the labelled set, with no model involved.

    The same three functions the signal engine calls, so the arm measures
    the shipped detection path rather than a re-implementation of it. It
    stops at detection: the cluster threshold and the cited-phrase evidence
    string are the pipeline test's ground, not this one's.

    `today` anchors a relative date in the content, so a run is reproducible
    across a year boundary. See ADR 0003.
    """
    from anveshak.analyst.mobilization import (
        extract_date,
        extract_place,
        find_calls_to_assemble,
        load_lexicon,
    )

    # An unresolvable lexicon loads as an empty one, by design, so that the
    # signal engine degrades visibly rather than crashing. Here that would
    # write precision 0.0 to a results file as though it were a measurement.
    if not load_lexicon().patterns:
        raise SystemExit(
            "The lexicon is empty, so this arm would measure nothing. "
            "Check MOBILIZATION_LEXICON_PATH."
        )

    predictions: list[dict[str, Any]] = []
    for example in examples:
        text = example["text"]
        language = example.get("language")
        if not find_calls_to_assemble(text, language=language):
            predictions.append({"is_call_to_assemble": False, "date": None, "place": None})
            continue
        when = extract_date(text, today=today)
        predictions.append(
            {
                "is_call_to_assemble": True,
                "date": when.isoformat() if when else None,
                "place": extract_place(text, language=language),
            }
        )
    return predictions


async def _predict(examples: list[dict[str, Any]], *, use_cloud: bool) -> list[dict[str, Any]]:
    """Run the confirmation prompt over the labelled set."""
    from anveshak.analyst.mobilization_confirm import (
        build_confirmation_prompt,
        parse_confirmation,
    )
    from anveshak.analyst.settings import settings
    from anveshak.llm import LLMProviderSettings, generate

    provider_settings = LLMProviderSettings()
    if use_cloud:
        provider_settings = LLMProviderSettings(llm_cloud_enabled=True)

    predictions: list[dict[str, Any]] = []
    for example in examples:
        # The same builder production uses, fencing included. Measuring an
        # unhardened prompt would not describe production behaviour.
        prompt = build_confirmation_prompt(example["text"])
        try:
            raw = await generate(
                prompt,
                local_model=settings.ollama_model,
                local_host=settings.ollama_host,
                local_timeout_s=settings.mobilization_confirm_timeout_s,
                max_tokens=settings.mobilization_confirm_max_tokens,
                settings=provider_settings,
            )
        except Exception as exc:
            print(f"  call failed: {exc}", file=sys.stderr)
            predictions.append({"is_call_to_assemble": False, "date": None, "place": None})
            continue

        result = parse_confirmation(raw)
        if result is None:
            # An unparseable answer is a wrong answer, not a skipped one.
            predictions.append({"is_call_to_assemble": False, "date": None, "place": None})
            continue

        predictions.append(
            {
                "is_call_to_assemble": result.is_call_to_assemble,
                "date": result.date.isoformat() if result.date else None,
                "place": result.place,
            }
        )
    return predictions


async def run(spec_path: Path, *, arms_to_run: list[str], today: date) -> dict[str, Any]:
    from anveshak.analyst.mobilization_confirm import (
        ACCEPTANCE_DATE_PLACE_ACCURACY,
        ACCEPTANCE_PRECISION,
        meets_acceptance_bars,
    )

    data = load_labelled_set(spec_path)
    examples = data["examples"]

    if data.get("provenance") != "public_reporting":
        print(
            "WARNING: this labelled set is not drawn from public reporting. "
            "Its numbers exercise the harness and do not decide whether the "
            "confirmation step ships. See benchmark/corpus/mobilization/README.md.",
            file=sys.stderr,
        )

    arms: dict[str, Any] = {}

    if "lexicon" in arms_to_run:
        from anveshak.analyst.mobilization import load_lexicon

        print(f"Lexicon, {len(examples)} examples...")
        arms["lexicon"] = score_predictions(predict_lexicon(examples, today=today), examples)
        # Without this a results file cannot be attributed to a vocabulary
        # after the fact, which is the one thing this arm exists to pin.
        arms["lexicon"]["lexicon_version"] = load_lexicon().version
        arms["lexicon"]["today"] = today.isoformat()

    if "local" in arms_to_run:
        print(f"Local model, {len(examples)} examples...")
        arms["local"] = score_predictions(await _predict(examples, use_cloud=False), examples)

    if "cloud" in arms_to_run:
        print(f"Cloud model, {len(examples)} examples...")
        arms["cloud"] = score_predictions(await _predict(examples, use_cloud=True), examples)

    # The bars are the confirmation step's, so they are decided only when
    # that arm ran. A lexicon-only run reports numbers and decides nothing.
    local = arms.get("local")
    ships = (
        meets_acceptance_bars(
            precision=local["precision"],
            date_place_accuracy=local["date_place_accuracy"],
        )
        if local is not None
        else None
    )

    result = {
        "run_at": datetime.now(UTC).isoformat(),
        "labelled_set": str(spec_path),
        "labelled_set_provenance": data.get("provenance"),
        "example_count": len(examples),
        "bars": {
            "precision": ACCEPTANCE_PRECISION,
            "date_place_accuracy": ACCEPTANCE_DATE_PLACE_ACCURACY,
        },
        "arms": arms,
        "local_meets_bars": ships,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"mobilization_{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json"
    out.write_text(json.dumps(result, indent=2))

    print(json.dumps(result["arms"], indent=2))
    if ships is None:
        print("\nThe local arm did not run, so the acceptance bars were not decided.")
    else:
        print(f"\nLocal meets both bars: {ships}")
        if not ships:
            print(
                "MOBILIZATION_CONFIRM_ENABLED stays false. The lexicon runs alone, "
                "which still cites the phrase that fired each signal."
            )
    print(f"Written to {out}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--set",
        dest="spec",
        type=Path,
        default=Path("benchmark/corpus/mobilization/labelled.yaml"),
    )
    parser.add_argument(
        "--arm",
        dest="arms",
        action="append",
        choices=["lexicon", "local", "cloud"],
        help=(
            "Arm to measure. Repeatable. Defaults to local, which is the arm "
            "the acceptance bars are about."
        ),
    )
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        default=REFERENCE_TODAY,
        help=(
            "Lexicon arm only. The date a relative expression in the content "
            "resolves against. Pinned by default, so a recorded number stays "
            "reproducible. The model arms read the date out of the prompt."
        ),
    )
    parser.add_argument(
        "--compare-cloud",
        action="store_true",
        help="Also measure a cloud model. Development environments only.",
    )
    args = parser.parse_args()

    if not args.spec.exists():
        print(f"No such labelled set: {args.spec}", file=sys.stderr)
        return 1

    arms_to_run = list(args.arms) if args.arms else ["local"]
    if args.compare_cloud and "cloud" not in arms_to_run:
        arms_to_run.append("cloud")

    asyncio.run(run(args.spec, arms_to_run=arms_to_run, today=args.today))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
