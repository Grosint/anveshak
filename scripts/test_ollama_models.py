"""Ollama LLM integration tests — runs INSIDE the report-worker container.

Tests Ollama connectivity, model availability, and structured output parsing
using the exact same code paths as production report generation.
Outputs JSON to stdout.

Usage (from host):
    docker cp scripts/test_ollama_models.py anveshak-report-worker-1:/tmp/
    docker exec anveshak-report-worker-1 python /tmp/test_ollama_models.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from typing import Any

os.environ["LOG_LEVEL"] = "ERROR"


def _result(test: str, passed: bool, detail: str, elapsed: float) -> dict[str, Any]:
    return {
        "test": test,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
        "elapsed_s": round(elapsed, 2),
    }


def _exc_detail(exc: BaseException, limit: int = 200) -> str:
    """Format an exception as type plus message.

    Many exceptions stringify to nothing: httpx.ReadTimeout is the one that cost
    time here, since a timed-out Ollama call was reported as `"detail": ""`, with
    only the elapsed_s hinting at what happened. The type alone is diagnostic.
    """
    message = str(exc).strip()
    return f"{type(exc).__name__}: {message}"[:limit] if message else type(exc).__name__


def _generation_or_error(resp: Any) -> tuple[str, str | None]:
    """Return (response_text, error) for an /api/generate reply.

    A non-2xx reply carries no `response` key, so reading it with .get() turns a
    server error into an empty string and the caller reports "response_length=0",
    which says nothing about why. Ollama's real message here was
    `llama-server process has terminated: signal: killed`, an OOM kill under
    memory pressure, and that is the one detail worth printing.
    """
    if resp.status_code >= 400:
        return "", f"HTTP {resp.status_code}: {resp.text[:200]}"
    return resp.json().get("response", ""), None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_ollama_reachable() -> dict:
    """Ollama API is reachable from this container."""
    import httpx
    from anveshak.reporter.settings import settings

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{settings.ollama_host}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
        elapsed = time.monotonic() - t0
        return _result("ollama_reachable", len(models) > 0, f"models: {', '.join(models)}", elapsed)
    except Exception as exc:
        return _result("ollama_reachable", False, _exc_detail(exc), time.monotonic() - t0)


async def test_configured_model_loaded() -> dict:
    """The configured Ollama model is actually loaded and available."""
    import httpx
    from anveshak.reporter.settings import settings

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{settings.ollama_host}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
        elapsed = time.monotonic() - t0
        configured = settings.ollama_model
        found = configured in models
        return _result(
            "configured_model_loaded",
            found,
            f"configured={configured}, available={models}",
            elapsed,
        )
    except Exception as exc:
        return _result("configured_model_loaded", False, _exc_detail(exc), time.monotonic() - t0)


async def test_llm_generates_response() -> dict:
    """Ollama generates a response to a simple prompt."""
    import httpx
    from anveshak.reporter.settings import settings

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{settings.ollama_host}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": "Respond with exactly: OK",
                    "stream": False,
                    "options": {"num_predict": 10},
                },
            )
            response_text, error = _generation_or_error(resp)
        elapsed = time.monotonic() - t0
        if error:
            return _result("llm_generates_response", False, error, elapsed)
        ok = len(response_text.strip()) > 0
        return _result(
            "llm_generates_response", ok, f"response_length={len(response_text)}", elapsed
        )
    except Exception as exc:
        return _result("llm_generates_response", False, _exc_detail(exc), time.monotonic() - t0)


async def test_llm_json_output() -> dict:
    """Ollama can produce JSON that parses successfully."""
    import httpx
    from anveshak.reporter.settings import settings

    t0 = time.monotonic()
    try:
        prompt = (
            "Return a JSON object with exactly these fields: "
            '{"summary": "test", "confidence": 0.5}. '
            "Return ONLY the JSON, no other text."
        )
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{settings.ollama_host}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 100},
                },
            )
            raw, error = _generation_or_error(resp)
        if error:
            return _result("llm_json_output", False, error, time.monotonic() - t0)

        # Try to parse JSON from the response (strip markdown fences if present)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        parsed = json.loads(cleaned)
        elapsed = time.monotonic() - t0
        has_fields = "summary" in parsed or "confidence" in parsed
        return _result(
            "llm_json_output", has_fields, f"parsed JSON with keys: {list(parsed.keys())}", elapsed
        )
    except json.JSONDecodeError as exc:
        return _result(
            "llm_json_output",
            False,
            f"JSON parse failed: {_exc_detail(exc, 100)}, raw: {raw[:100]}",
            time.monotonic() - t0,
        )
    except Exception as exc:
        return _result("llm_json_output", False, _exc_detail(exc), time.monotonic() - t0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main():
    results = []
    for test_fn in [
        test_ollama_reachable,
        test_configured_model_loaded,
        test_llm_generates_response,
        test_llm_json_output,
    ]:
        results.append(await test_fn())

    sys.__stdout__.write(json.dumps(results, indent=2) + "\n")
    sys.__stdout__.flush()

    passed = sum(1 for r in results if r["status"] == "PASS")
    total = len(results)
    sys.__stdout__.write(f"\nOllama models: {passed}/{total} passed\n")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
