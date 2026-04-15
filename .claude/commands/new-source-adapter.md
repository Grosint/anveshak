Create a complete, production-ready source adapter for: $ARGUMENTS

A source adapter ingests content from one platform/source into Anveshak's content pipeline.
Every adapter MUST ship with unit tests, integration tests, and pass the SourceAdapterConformanceSuite.

## Step 0 — Parse arguments
Extract:
- adapter_name: snake_case (e.g. telegram_channel)
- adapter_id: kebab-case (e.g. telegram-channel-v1)
- platform: one of web|telegram|twitter|reddit|bluesky|rss|upload
- trigger_mode: one of polling|streaming|task|upload

If ambiguous, STOP and ask.

## Step 1 — Read context
Read: .claude/skills/source-adapter-sdk.md
Read: CLAUDE.md (hardware independence rule, labels mandatory, reports immutable)

## Step 2 — Create adapter
Create services/social/anveshak/social/adapters/{adapter_name}/ with:
- adapter.py — implements SourceAdapterBase
- config.py — pydantic-settings, env_prefix, all hardware-sensitive values from env
- __init__.py

Rules:
- Every ContentItem MUST have labels set
- content_hash MUST be SHA-256 of clean_text (deduplication key)
- credentials ALWAYS from environment variables, never hardcoded
- X_MONTHLY_READ_CAP must be respected in any X/Twitter adapter

## Step 3 — Register in settings
Add adapter_id to services/social/anveshak/social/settings.py ENABLED_ADAPTERS list

## Step 4 — Write unit tests
tests/unit/social/test_{adapter_name}_parser.py
- happy path, malformed input, missing fields, labels non-optional

## Step 5 — Write integration test
tests/integration/social/test_{adapter_name}_integration.py
- requires running service, real content fetched (or fixture injected)

## Step 6 — Conformance
Run: uv run pytest tests/unit/social/test_{adapter_name}_*.py -v
Report pass/fail for all assertions.

## Step 7 — Final checklist
- [ ] Implements SourceAdapterBase
- [ ] Every ContentItem has labels
- [ ] content_hash set on every item
- [ ] Credentials from env vars only
- [ ] Hardware-sensitive config in settings not hardcoded
- [ ] Unit tests passing
- [ ] Integration test written
- [ ] Registered in ENABLED_ADAPTERS
