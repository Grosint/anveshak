"""Social adapter connectivity test — runs INSIDE the scrape-social-scheduler container.

Tests Telegram, X/Twitter, and Reddit using the exact same adapter code
as production. Outputs JSON to stdout for the host orchestrator.

Usage (from host):
    docker exec anveshak-scrape-social-scheduler-1 python /tmp/test_scrape_social.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import traceback
from typing import Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _result(
    source_type: str,
    name: str,
    passed: bool,
    chars: int,
    reason: str,
    elapsed: float,
) -> dict[str, Any]:
    return {
        "type": source_type,
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "chars": chars,
        "reason": reason,
        "elapsed_s": round(elapsed, 1),
    }


# ---------------------------------------------------------------------------
# Telegram test — uses real TelegramAdapter.authenticate() + collect()
# ---------------------------------------------------------------------------


async def test_telegram() -> list[dict]:
    from anveshak.social.settings import settings

    if not settings.telegram_adapter_enabled:
        return [_result("telegram", "(disabled)", False, 0, "TELEGRAM_ADAPTER_ENABLED=false", 0)]

    from anveshak.social.adapters.base import AdapterAuthError
    from anveshak.social.adapters.telegram import TelegramAdapter

    adapter = TelegramAdapter()
    results = []

    # Authenticate
    t0 = time.monotonic()
    try:
        await adapter.authenticate()
        auth_elapsed = time.monotonic() - t0
    except AdapterAuthError as exc:
        auth_elapsed = time.monotonic() - t0
        return [_result("telegram", "auth", False, 0, str(exc)[:120], auth_elapsed)]
    except Exception as exc:
        auth_elapsed = time.monotonic() - t0
        return [_result("telegram", "auth", False, 0, str(exc)[:120], auth_elapsed)]

    if adapter._client is None:
        return [_result("telegram", "auth", False, 0, "Client not initialized", auth_elapsed)]

    results.append(_result("telegram", "auth", True, 0, "Session authorized", auth_elapsed))

    # Collect from test channels — known active Indian defence channels
    test_channels = [
        os.environ.get("TELEGRAM_TEST_CHANNEL", "@DSquadOfficial"),
        "@indianmilitarynews",
    ]
    for test_channel in test_channels:
        t0 = time.monotonic()
        try:
            items = []
            async for item in adapter.collect(
                topic_keywords=["defence", "military"],
                source_handles=[test_channel],
                topic_id="test-00000000",
            ):
                items.append(item)
                if len(items) >= 5:  # cap at 5 for testing
                    break

            elapsed = time.monotonic() - t0
            if items:
                total_chars = sum(len(it.raw_text) for it in items)
                results.append(
                    _result(
                        "telegram",
                        test_channel,
                        True,
                        total_chars,
                        f"{len(items)} messages fetched",
                        elapsed,
                    )
                )
            else:
                results.append(
                    _result(
                        "telegram",
                        test_channel,
                        False,
                        0,
                        "No messages returned",
                        elapsed,
                    )
                )
        except Exception as exc:
            elapsed = time.monotonic() - t0
            results.append(_result("telegram", test_channel, False, 0, str(exc)[:120], elapsed))

    # Disconnect cleanly
    try:
        await adapter._client.disconnect()
    except Exception:
        pass

    return results


# ---------------------------------------------------------------------------
# X/Twitter test — uses real make_x_adapter() + authenticate() + collect()
# ---------------------------------------------------------------------------


async def test_x() -> list[dict]:
    from anveshak.social.settings import settings

    if not settings.x_adapter_enabled:
        return [_result("x", "(disabled)", False, 0, "X_ADAPTER_ENABLED=false", 0)]

    if not settings.x_bearer_token:
        return [_result("x", "(no token)", False, 0, "X_BEARER_TOKEN not set", 0)]

    from anveshak.social.adapters.base import AdapterAuthError, AdapterRateLimitError
    from anveshak.social.adapters.x_adapter import make_x_adapter
    from arq import create_pool
    from arq.connections import RedisSettings

    results = []

    # Need Redis for the spend guard
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    except Exception as exc:
        return [_result("x", "redis", False, 0, f"Redis connection failed: {str(exc)[:80]}", 0)]

    adapter = make_x_adapter(redis)

    # Authenticate
    t0 = time.monotonic()
    try:
        await adapter.authenticate()
        auth_elapsed = time.monotonic() - t0
    except AdapterAuthError as exc:
        auth_elapsed = time.monotonic() - t0
        await redis.close()
        return [_result("x", "auth", False, 0, str(exc)[:120], auth_elapsed)]
    except Exception as exc:
        auth_elapsed = time.monotonic() - t0
        await redis.close()
        return [_result("x", "auth", False, 0, str(exc)[:120], auth_elapsed)]

    results.append(_result("x", "auth", True, 0, "Bearer token accepted", auth_elapsed))

    # Search with test keywords — use multiple broad terms for better hit rate
    # The adapter's collect() wraps each keyword in quotes and joins with OR
    test_keywords = ["Indian Army", "Indian Navy", "Indian Air Force", "India military"]
    display_name = "India military/defence"
    t0 = time.monotonic()
    try:
        items = []
        async for item in adapter.collect(
            topic_keywords=test_keywords,
            source_handles=[],
            topic_id="test-00000000",
        ):
            items.append(item)

        elapsed = time.monotonic() - t0
        if items:
            total_chars = sum(len(it.raw_text) for it in items)
            results.append(
                _result(
                    "x",
                    f"keywords: {display_name}",
                    True,
                    total_chars,
                    f"{len(items)} tweets found",
                    elapsed,
                )
            )
        else:
            results.append(
                _result(
                    "x",
                    f"keywords: {display_name}",
                    False,
                    0,
                    "No tweets returned (spend cap / no results / API tier)",
                    elapsed,
                )
            )
    except AdapterRateLimitError as exc:
        elapsed = time.monotonic() - t0
        results.append(
            _result(
                "x",
                f"keywords: {display_name}",
                False,
                0,
                f"Rate limited: {str(exc)[:80]}",
                elapsed,
            )
        )
    except Exception as exc:
        elapsed = time.monotonic() - t0
        results.append(_result("x", f"keywords: {display_name}", False, 0, str(exc)[:120], elapsed))

    await redis.close()
    return results


# ---------------------------------------------------------------------------
# Reddit test — uses real RedditAdapter.authenticate() + collect()
# ---------------------------------------------------------------------------


async def test_reddit() -> list[dict]:
    from anveshak.social.settings import settings

    if not settings.reddit_adapter_enabled:
        return [_result("reddit", "(disabled)", False, 0, "REDDIT_ADAPTER_ENABLED=false", 0)]

    if not settings.reddit_client_id or not settings.reddit_client_secret:
        return [
            _result(
                "reddit",
                "(no credentials)",
                False,
                0,
                "REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set",
                0,
            )
        ]

    from anveshak.social.adapters.base import AdapterAuthError
    from anveshak.social.adapters.reddit import RedditAdapter

    adapter = RedditAdapter()
    results = []

    # Authenticate
    t0 = time.monotonic()
    try:
        await adapter.authenticate()
        auth_elapsed = time.monotonic() - t0
    except AdapterAuthError as exc:
        auth_elapsed = time.monotonic() - t0
        return [_result("reddit", "auth", False, 0, str(exc)[:120], auth_elapsed)]
    except Exception as exc:
        auth_elapsed = time.monotonic() - t0
        return [_result("reddit", "auth", False, 0, str(exc)[:120], auth_elapsed)]

    results.append(_result("reddit", "auth", True, 0, "PRAW authenticated", auth_elapsed))

    # Fetch from a test subreddit
    test_sub = "r/worldnews"
    t0 = time.monotonic()
    try:
        items = []
        async for item in adapter.collect(
            topic_keywords=["world"],
            source_handles=[test_sub],
            topic_id="test-00000000",
        ):
            items.append(item)
            if len(items) >= 5:
                break

        elapsed = time.monotonic() - t0
        if items:
            total_chars = sum(len(it.raw_text) for it in items)
            results.append(
                _result(
                    "reddit",
                    test_sub,
                    True,
                    total_chars,
                    f"{len(items)} posts fetched",
                    elapsed,
                )
            )
        else:
            results.append(
                _result(
                    "reddit",
                    test_sub,
                    False,
                    0,
                    "No posts returned",
                    elapsed,
                )
            )
    except Exception as exc:
        elapsed = time.monotonic() - t0
        results.append(_result("reddit", test_sub, False, 0, str(exc)[:120], elapsed))

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> list[dict]:
    results: list[dict] = []
    results.extend(await test_telegram())
    results.extend(await test_x())
    results.extend(await test_reddit())
    return results


if __name__ == "__main__":
    try:
        results = asyncio.run(main())
        print(json.dumps(results))
    except Exception:
        print(
            json.dumps(
                [
                    {
                        "type": "error",
                        "name": "social_test",
                        "status": "FAIL",
                        "chars": 0,
                        "reason": traceback.format_exc()[-200:],
                        "elapsed_s": 0,
                    }
                ]
            )
        )
        sys.exit(1)
