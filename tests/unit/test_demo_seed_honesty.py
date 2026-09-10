"""No seed may fabricate detection output - issue #40.

A Signal or a Narrative Cluster written by hand is decoration, not detection.
Neither may be shown to an evaluating officer as something the platform found.

The guard globs every `scripts/seed_*.sql` and denies by default, so a new seed
is covered the day it is added rather than the day someone remembers to list
it. Seeds that still fabricate are named in KNOWN_FABRICATING with a reason,
following the EXEMPT_MODELS pattern in scripts/verify_labels.py. That list is
debt made visible; it must only ever shrink.

Publication Time is checked here as a column-list assertion only. Whether every
seeded row actually carries a value is a database question, and is asserted in
tests/integration/test_demo_seed.py.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = REPO_ROOT / "scripts"
DEMO_SEED = SEED_DIR / "seed_demo.sql"

# Agency demonstration seeds that still insert Signals and Narrative Clusters.
# Issue #40 scoped the fix to the demonstration seed only; each of these needs
# the same treatment and a corroborating corpus of its own before it can be
# removed from this list.
KNOWN_FABRICATING = {
    "seed_demo_full.sql": "#40 covered seed_demo.sql only; full-corpus variant not yet migrated",
    "seed_demo_engine_c.sql": "#40 covered seed_demo.sql only; Engine C 4-agency scenarios",
    "seed_airforce_bengaluru_demo.sql": "#40 covered seed_demo.sql only; IAF Bengaluru scenario",
    "seed_bidadi_demo.sql": "#40 covered seed_demo.sql only; Bidadi scenario",
    "seed_kerala_demo.sql": "#40 covered seed_demo.sql only; Kerala scenario",
    "seed_haryana_demo.sql": "#40 covered seed_demo.sql only; Haryana scenario",
    "seed_nagaland_demo.sql": "#40 covered seed_demo.sql only; Nagaland scenario",
    "seed_ncb_demo.sql": "#40 covered seed_demo.sql only; NCB scenario",
}

FABRICATED_INSERTS = (
    (r"INSERT\s+INTO\s+signals\b", "a Signal the engine did not fire"),
    (r"INSERT\s+INTO\s+narrative_clusters\b", "a Narrative Cluster clustering did not produce"),
)


def _guarded_seeds() -> list[Path]:
    return sorted(p for p in SEED_DIR.glob("seed_*.sql") if p.name not in KNOWN_FABRICATING)


def _content_item_columns(sql: str) -> list[str]:
    match = re.search(r"INSERT\s+INTO\s+content_items\s*\((?P<cols>[^)]*)\)", sql, re.IGNORECASE)
    assert match is not None, "no content_items INSERT found"
    return [col.strip().lower() for col in match.group("cols").split(",")]


class TestNoFabricatedDetection:
    def test_guarded_seeds_fabricate_nothing(self) -> None:
        offenders: list[str] = []
        for seed in _guarded_seeds():
            sql = seed.read_text(encoding="utf-8")
            for pattern, what in FABRICATED_INSERTS:
                if re.search(pattern, sql, re.IGNORECASE):
                    offenders.append(f"{seed.name} inserts {what}")
        assert not offenders, "seeds fabricating detection output: " + "; ".join(offenders)

    def test_the_demonstration_seed_is_guarded(self) -> None:
        # Guarding by glob is only meaningful if the file this issue fixed is
        # actually in the set rather than quietly exempted.
        assert DEMO_SEED in _guarded_seeds()

    def test_exemptions_name_real_files_and_carry_a_reason(self) -> None:
        for name, reason in KNOWN_FABRICATING.items():
            assert (SEED_DIR / name).exists(), f"exemption names a missing file: {name}"
            assert reason.strip(), f"exemption without a reason: {name}"

    def test_demo_seed_assigns_no_cluster_to_content(self) -> None:
        columns = _content_item_columns(DEMO_SEED.read_text(encoding="utf-8"))
        assert "narrative_cluster_id" not in columns, (
            "seeded content must not be pre-assigned to a cluster; clustering assigns it"
        )

    def test_demo_seed_retires_the_rows_it_used_to_fabricate(self) -> None:
        """A rerun must clean up a box seeded before #40.

        Every INSERT here is ON CONFLICT DO NOTHING, so removing the INSERTs
        alone leaves the old hand-written rows on screen forever.
        """
        sql = DEMO_SEED.read_text(encoding="utf-8")
        for retired in (
            "11000000-0000-0000-0000-000000000001",
            "00000001-0000-0000-0000-000000000001",
            "00000001-0000-0000-0000-000000000002",
        ):
            assert retired in sql, f"seed never retires the fabricated row {retired}"
        assert re.search(r"DELETE\s+FROM\s+signals\b", sql, re.IGNORECASE)
        assert re.search(r"DELETE\s+FROM\s+narrative_clusters\b", sql, re.IGNORECASE)


class TestPublicationTime:
    def test_content_items_carry_publication_time(self) -> None:
        columns = _content_item_columns(DEMO_SEED.read_text(encoding="utf-8"))
        assert "published_at" in columns, (
            "seeded content without published_at falls into the Sentiment "
            "Timeline's excluded count and the chart renders empty"
        )

    def test_content_items_still_carry_capture_time(self) -> None:
        # Both, and visibly different values. The glossary draws a distinction
        # between the two and the seed has to exercise it.
        columns = _content_item_columns(DEMO_SEED.read_text(encoding="utf-8"))
        assert "captured_at" in columns
