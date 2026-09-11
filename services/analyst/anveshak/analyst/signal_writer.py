"""Shared signal-writing primitives.

Extracted from signal_engine.py, which was doing two jobs at once: it owned
these primitives and it was also the orchestrator that calls every detector.
Every new detector therefore had to import from the module that imports it,
and manufactured.py and mobilization.py worked around the cycle with
function-body imports.

Two consequences beyond style, both of which had already bitten:

  - mobilization.py had pushed json, uuid, datetime and its metrics import
    into a function body, against the module conventions.
  - A deferred name is not a module attribute, so
    patch("...signal_engine.check_mobilization_calls") could not work, which
    is how a missing term in the cycle total shipped green.

Every detector now imports from here at module scope, and signal_engine is
only the orchestrator.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Awaitable, Callable

from anveshak.db import DBConnection

BroadcastFn = Callable[[dict], Awaitable[None]]

SQL_INSERT_SIGNAL = """
    INSERT INTO signals (
        id, topic_id, cluster_id, signal_type, description, evidence,
        status, created_at, updated_at, labels
    )
    VALUES ($1, $2, $3, $4, $5, $6::jsonb, 'new', $7, $7,
            '{"classification":"OPEN","domain":"osint","owner_org":"anveshak"}'::jsonb)
    RETURNING id
"""

# The dedup window is measured back from the reference time the pass runs at,
# not from NOW(). A Replay stage that dedup'd against the wall clock would
# compare a simulated signal against 24 hours of real time and fire every
# stage, or none. See ADR 0003.
SQL_DUPLICATE_SIGNAL_CHECK = """
    SELECT id FROM signals
    WHERE cluster_id  = $1
      AND signal_type = $2
      AND created_at  > $3::timestamptz - INTERVAL '24 hours'
    LIMIT 1
"""

SQL_DUPLICATE_TOPIC_SIGNAL_CHECK = """
    SELECT id FROM signals
    WHERE topic_id = $1
      AND signal_type = $2
      AND created_at > $3::timestamptz - INTERVAL '24 hours'
    LIMIT 1
"""


async def is_duplicate_signal(
    conn: DBConnection,
    cluster_id: str,
    signal_type: str,
    now: datetime | None = None,
) -> bool:
    """True if an identical signal fired within the 24h before `now`.

    Criteria 2.13. `now` defaults to the current time.
    """
    reference = now if now is not None else datetime.now(UTC)
    row = await conn.fetchrow(SQL_DUPLICATE_SIGNAL_CHECK, cluster_id, signal_type, reference)
    return row is not None
