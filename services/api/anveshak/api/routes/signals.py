"""Signals endpoints — threshold-based intelligence notifications (Phase 2, criteria 2.14–2.20)."""
from __future__ import annotations

import asyncio
from datetime import datetime, UTC

import asyncpg
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect

from ..auth.jwt import get_current_user
from ..db.pool import get_db, get_pool
from ..db import signals as signals_db

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/signals", tags=["signals"])

# ---------------------------------------------------------------------------
# WebSocket connection registry
# ---------------------------------------------------------------------------

# Map of analyst_session_id → (WebSocket, connected_at datetime)
_sessions: dict[str, tuple[WebSocket, datetime]] = {}


async def broadcast_signal(signal: dict) -> None:
    """Push a new signal to all connected analyst sessions (criteria 2.18).

    Dead connections are cleaned up. Schema per criteria 2.19:
    {"type": "signal", "signal_id": ..., "topic_id": ..., "severity": ...}
    """
    dead: list[str] = []
    for session_id, (ws, _) in list(_sessions.items()):
        try:
            await ws.send_json(signal)
        except Exception:
            dead.append(session_id)

    for session_id in dead:
        _sessions.pop(session_id, None)
        log.debug("signals.ws_dead_removed", session_id=session_id)


# ---------------------------------------------------------------------------
# WebSocket endpoint (criteria 2.17, 2.18, 2.20)
# ---------------------------------------------------------------------------

@router.websocket("/ws/{analyst_session_id}")
async def signal_websocket(
    websocket: WebSocket,
    analyst_session_id: str,
    token: str = Query(..., description="Bearer JWT token — same token used for REST endpoints"),
    since: str | None = Query(default=None, description="ISO datetime — replay missed signals after this timestamp"),
):
    """WebSocket endpoint for real-time signal delivery to analyst sessions.

    - Authenticated via ?token= query param (criteria 2.17)
    - On connect: replays signals missed since `since` timestamp (criteria 2.20)
    - Sends keep-alive ping every 30s
    - Status flow: new → acknowledged → dismissed (criteria 2.14)
    """
    from ..auth.jwt import verify_token
    try:
        verify_token(token)
    except Exception:
        await websocket.close(code=4001)
        return

    await websocket.accept()

    connected_at = datetime.now(UTC)
    _sessions[analyst_session_id] = (websocket, connected_at)
    log.info("signals.ws_connected", session_id=analyst_session_id)

    # Replay missed signals if client provides a reconnect timestamp (criteria 2.20)
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            # Fetch from DB using a direct connection — websocket handler can't use Depends
            pool = get_pool()
            if pool:
                async with pool.acquire() as conn:
                    missed = await signals_db.get_missed_signals(conn, since_dt)
                    for row in missed:
                        await websocket.send_json({
                            "type": "signal_replay",
                            "signal_id": row["id"],
                            "topic_id": row["topic_id"],
                            "cluster_id": row["cluster_id"],
                            "signal_type": row["signal_type"],
                            "created_at": row["created_at"].isoformat(),
                        })
                    log.info(
                        "signals.ws_replay_sent",
                        session_id=analyst_session_id,
                        count=len(missed),
                    )
        except Exception as exc:
            log.warning("signals.ws_replay_failed", error=str(exc))

    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        _sessions.pop(analyst_session_id, None)
        log.info("signals.ws_disconnected", session_id=analyst_session_id)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_signals(
    status: str = Query(default="new", pattern="^(new|acknowledged|dismissed)$"),
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List signals by status (criteria 2.14 status flow)."""
    return await signals_db.list_signals(db, status)


@router.patch("/{signal_id}/acknowledge")
async def acknowledge_signal(
    signal_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Transition signal: new → acknowledged (criteria 2.15)."""
    row = await signals_db.acknowledge_signal(db, signal_id, datetime.now(UTC))
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found or not in 'new' state")
    return {"signal_id": signal_id, "status": "acknowledged"}


@router.patch("/{signal_id}/dismiss")
async def dismiss_signal(
    signal_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Transition signal: new|acknowledged → dismissed (criteria 2.16)."""
    row = await signals_db.dismiss_signal(db, signal_id, datetime.now(UTC))
    if not row:
        raise HTTPException(
            status_code=404,
            detail="Signal not found or already dismissed",
        )
    return {"signal_id": signal_id, "status": "dismissed"}
