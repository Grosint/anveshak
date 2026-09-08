"""Mobilization confirmation benchmark — issue #34.

Measures a model against a labelled set on two bars:

  detection precision            at least 0.85
  date and place exact match     at least 0.70

Precision is weighted over recall. A false mobilization alert about a
political group is the worst output this system can produce, and the lexicon
already catches the obvious cases, so lower recall is tolerable.

Run:

    uv run python -m benchmark.mobilization \\
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
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

import yaml

RESULTS_DIR = Path("benchmark/results")


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

    Extraction accuracy is computed only where the truth is a call to
    assemble: a correct null on a non-call says nothing about extraction.
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

        if is_call:
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


async def run(spec_path: Path, *, compare_cloud: bool) -> dict[str, Any]:
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

    print(f"Local model, {len(examples)} examples...")
    arms["local"] = score_predictions(
        await _predict(examples, use_cloud=False), examples
    )

    if compare_cloud:
        print(f"Cloud model, {len(examples)} examples...")
        arms["cloud"] = score_predictions(
            await _predict(examples, use_cloud=True), examples
        )

    local = arms["local"]
    ships = meets_acceptance_bars(
        precision=local["precision"],
        date_place_accuracy=local["date_place_accuracy"],
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
        "--compare-cloud",
        action="store_true",
        help="Also measure a cloud model. Development environments only.",
    )
    args = parser.parse_args()

    if not args.spec.exists():
        print(f"No such labelled set: {args.spec}", file=sys.stderr)
        return 1

    asyncio.run(run(args.spec, compare_cloud=args.compare_cloud))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
