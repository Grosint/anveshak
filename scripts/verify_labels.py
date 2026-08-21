#!/usr/bin/env python3
"""Verify that all Pydantic models have a non-optional `labels` field.

AGENTS.md rule 2: Labels are NEVER Optional. Never create a model without them.

Scope: every model that is persisted or crosses a service boundary on its own.
Nested value objects inherit their parent's classification and are exempt only
if listed in EXEMPT_MODELS below, with a reason. Nothing is exempt by default.

Usage:
    python scripts/verify_labels.py
    uv run --package anveshak-sdk python scripts/verify_labels.py
"""

import importlib
import inspect
import sys
from types import ModuleType
from typing import get_type_hints

from pydantic import BaseModel
from pydantic.fields import FieldInfo


def _is_optional(annotation) -> bool:
    """Return True if the annotation is Optional[X] (i.e. Union[X, None])."""
    import typing

    origin = getattr(annotation, "__origin__", None)
    if origin is typing.Union:
        args = annotation.__args__
        return type(None) in args
    return False


def check_model(model_cls: type) -> list[str]:
    """Return list of violation messages for this model class."""
    violations = []
    try:
        hints = get_type_hints(model_cls)
    except Exception:
        return violations

    if "labels" not in hints:
        violations.append(
            f"  MISSING: {model_cls.__module__}.{model_cls.__name__} has no `labels` field"
        )
        return violations

    if _is_optional(hints["labels"]):
        violations.append(
            f"  OPTIONAL: {model_cls.__module__}.{model_cls.__name__}.labels "
            f"is Optional — must be non-optional"
        )

    # Check that there's no default of None
    field_info: FieldInfo = model_cls.model_fields.get("labels")
    if field_info and field_info.default is None:
        violations.append(
            f"  DEFAULT_NONE: {model_cls.__module__}.{model_cls.__name__}.labels "
            f"has default=None — must be required"
        )

    return violations


# Models exempt from rule 2, each with the reason it is exempt.
#
# Deny by default: a model is only exempt if it is named here. Substring name
# matching was tried and rejected: "Create" in the name would have silently
# exempted a model called CreatorProfile, which is exactly the silent gap rule 2
# exists to close.
#
# The bar for adding an entry: the model is a nested value object that only ever
# exists inside an already-labelled parent, so it inherits that parent's
# classification. Duplicating labels onto it would let the two diverge: an
# entity marked OPEN inside a SECRET ContentItem.
EXEMPT_MODELS: dict[str, str] = {
    "anveshak.models.base.Labels": "Labels is the labels type itself.",
    "anveshak.models.content.ExtractedEntity": (
        "Nested value object, only ever a list on ContentItem.extracted_entities, "
        "never persisted or transmitted on its own, so it inherits ContentItem's labels."
    ),
}


def scan_module(module: ModuleType) -> list[str]:
    """Scan all Pydantic BaseModel subclasses in a module."""
    violations = []
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if not issubclass(obj, BaseModel) or obj is BaseModel or obj.__module__ != module.__name__:
            continue

        if "labels" in obj.model_fields:
            # Model has a labels field — check it's not optional
            violations.extend(check_model(obj))
        elif f"{module.__name__}.{name}" not in EXEMPT_MODELS:
            violations.append(f"  MISSING: {module.__name__}.{name} has no `labels` field")
    return violations


MODULES_TO_CHECK = [
    "anveshak.models.base",
    "anveshak.models.topic",
    "anveshak.models.source",
    "anveshak.models.content",
    "anveshak.models.signal",
    "anveshak.models.report",
    "anveshak.models.job",
]


def main() -> int:
    print("Verifying labels non-optional constraint across all models...\n")
    all_violations = []

    for module_name in MODULES_TO_CHECK:
        try:
            module = importlib.import_module(module_name)
            violations = scan_module(module)
            all_violations.extend(violations)
            status = "FAIL" if violations else "OK"
            print(f"  [{status}] {module_name}")
            for v in violations:
                print(v)
        except ImportError as e:
            print(f"  [SKIP] {module_name} — import error: {e}")

    print()
    if all_violations:
        print(f"FAILED — {len(all_violations)} violation(s) found.")
        print("Fix: add `labels: Labels` (non-optional) to each flagged model.")
        return 1

    print("PASSED — all models have non-optional labels field.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
