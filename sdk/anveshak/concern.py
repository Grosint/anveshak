"""Concern taxonomy scoring and filtering — issue #36, ADR 0001.

Lives in the SDK because both services need it: the analyst scores content
against the taxonomy at ingest, and the API filters clusters by it. The API
image does not contain the analyst package, so this cannot live there.

Categories are filters the analyst chooses to apply. They change which
narratives appear in a list. They never change the order of the ones that
remain, and the system never surfaces a category unprompted.

That constraint is why this module has no ordering function and why nothing
downstream reads a concern score as a sort key. Ranking by how concerning
the system judges content to be, applied to lawful political organising,
would make this a dissent detector. Ranking on propagation keeps it factual
and auditable, and as it happens makes it better at the job, because the
pattern worth finding is identifiable behaviourally.

The taxonomy itself is a versioned file the customer owns. Nothing here
knows any category by name.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import structlog
import yaml

from .concern_settings import ConcernSettings

settings = ConcernSettings()

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ConcernCategory:
    id: str
    label: str
    definition: str
    keywords: list[str]


@dataclass(frozen=True)
class ConcernTaxonomy:
    version: int
    owner: str
    categories: list[ConcernCategory]


def _resolve_taxonomy_path() -> Optional[Path]:
    """Find the taxonomy in the container or in a host checkout.

    Same lookup shape as the mobilization lexicon and the geocoder's custom
    locations: configured path, container mounts, then the repository root
    located by its uv.lock marker.
    """
    configured = Path(settings.concern_taxonomy_path)
    if configured.is_file():
        return configured

    project_root = Path(__file__).resolve().parent
    while project_root != project_root.parent:
        if (project_root / "uv.lock").exists():
            break
        project_root = project_root.parent

    relative = Path("infra/configs/taxonomies/concern.yaml")
    for candidate in (
        Path("/app") / relative,
        Path("/workspace") / relative,
        project_root / relative,
    ):
        if candidate.is_file():
            return candidate
    return None


@lru_cache(maxsize=1)
def load_taxonomy() -> ConcernTaxonomy:
    """Read the versioned taxonomy file.

    A missing file logs the reason and yields an empty taxonomy, so the
    facet is visibly unavailable rather than quietly absent.
    """
    resolved = _resolve_taxonomy_path()
    if resolved is None:
        log.warning(
            "concern.taxonomy_missing",
            path=settings.concern_taxonomy_path,
            reason="CONCERN_TAXONOMY_PATH does not exist, the facet is unavailable",
        )
        return ConcernTaxonomy(version=0, owner="", categories=[])

    raw: dict[str, Any] = yaml.safe_load(resolved.read_text()) or {}
    categories = [
        ConcernCategory(
            id=entry["id"],
            label=entry["label"],
            definition=entry.get("definition", ""),
            keywords=[str(k).lower() for k in entry.get("keywords", [])],
        )
        for entry in raw.get("categories", [])
    ]

    log.info(
        "concern.taxonomy_loaded",
        version=raw.get("version", 0),
        categories=len(categories),
        path=str(resolved),
    )
    return ConcernTaxonomy(
        version=int(raw.get("version", 0)),
        owner=str(raw.get("owner", "")),
        categories=categories,
    )


def score_against_taxonomy(text: str) -> dict[str, int]:
    """Return matched pattern counts per category, omitting categories at zero.

    A count of matched patterns rather than an opaque model output, so an
    analyst can open the taxonomy file and check why a narrative carries a
    category. The score exists to answer "does this belong in my filter?",
    and nothing else reads it.
    """
    if not text:
        return {}

    lowered = text.lower()
    scores: dict[str, int] = {}
    for category in load_taxonomy().categories:
        hits = sum(1 for keyword in category.keywords if keyword in lowered)
        if hits:
            scores[category.id] = hits
    return scores


def apply_filter(items: list[dict[str, Any]], *, categories: list[str]) -> list[dict[str, Any]]:
    """Keep items carrying any of the named categories, in their existing order.

    Membership changes; ordering does not. The caller has already ordered by
    a measurement of propagation, and this function must not disturb it.
    There is deliberately no variant of this function that sorts.
    """
    if not categories:
        return list(items)

    wanted = set(categories)
    return [item for item in items if wanted & set((item.get("concern") or {}).keys())]
