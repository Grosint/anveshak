# Script-blind quality gate, and the reporter's hardcoded embed timeout

Two defects found while running the Cockroach Janta Party Replay (issue #47 driver, `scripts/replay_corpus.py`).
Both are small in code and large in effect: together they cost the Replay its Hindi coverage and both of its reports.

## Defect 1: the content quality gate discriminates by script

`services/analyst/anveshak/analyst/content_quality.py:40` rejects content on a raw character count:

```python
if len(stripped) < settings.content_min_length:
    return (False, "too_short")
```

`content_min_length` defaults to 100 (`services/analyst/anveshak/analyst/settings.py:208`).

A character count is a proxy for content volume that only holds for Latin script.
Devanagari carries the same meaning in far fewer characters, so a complete Hindi news sentence fails a threshold the equivalent English sentence clears comfortably.

The module already has a script-aware word regex at line 44 covering Devanagari, Arabic, Cyrillic, Bengali and CJK.
The character gate runs before it and discards the item first.

### What it cost

Six items, every one of them Hindi, every one of them load-bearing for phases 3 to 5 of the corpus:

| published_at | source | chars | words | unique ratio | subject |
|---|---|---|---|---|---|
| 2026-07-01 | Rashtra Darpan | 89 | 19 | 0.89 | Ranchi police refuse march permission |
| 2026-07-05 | Rashtra Darpan | 90 | 19 | 0.89 | Delhi police refuse |
| 2026-07-07 | Rashtra Darpan | 89 | 19 | 0.89 | Bhopal police refuse |
| 2026-07-20 | Rashtra Darpan | 99 | 19 | 1.00 | Sansad Chalo march, police barricades |
| 2026-07-21 | Samachar 24 | 97 | 18 | 1.00 | lathicharge, activists injured |
| 2026-07-23 | Samachar 24 | 83 | 16 | 0.94 | judicial inquiry ordered |

Every one passes the unique-word-ratio floor of 0.4 with room to spare.
Every one carries 16 or more words.
They fail only the blind character count.

### Calibration

Measured across all 158 items of `corpora/synthetic_cockroach_janta_party.jsonl`, using the module's own word regex:

| Gate | Items dropped |
|---|---|
| `chars >= 100` (current) | 9 of 158, all 9 Hindi, 0 English |
| `words >= 8` | 0 of 158 |
| `words >= 10` | 0 of 158 |
| `words >= 12` | 0 of 158 |
| `words >= 15` | 0 of 158 |

The character gate is the only check in the module that discriminates by script, and it is the only check these items fail.
The smallest genuine item in the corpus carries 16 words.

## Defect 2: hardcoded timeout on the reporter's RAG embedding call

`services/reporter/anveshak/reporter/rag.py:41`:

```python
async with httpx.AsyncClient(timeout=30) as client:
    resp = await client.post(f"{settings.analyst_service_url}/internal/embed", ...)
```

The literal 30 violates architectural rule 6: no performance-sensitive parameter is hardcoded in service code.

It is also not survivable in practice.
The call reaches the analyst service, which during a Replay is saturated embedding content on CPU.
The Replay died at stage 11 of 17 with `httpx.ReadTimeout` after 31.10 seconds.

The reporter's LLM timeout is configured correctly at 540 seconds (`OLLAMA_REPORT_TIMEOUT_S`, `infra/compose.yml:721`) and never got the chance to matter, because the RAG query embedding fails first.

## Fixes

### A. Word-count gate in the analyst

In `services/analyst/anveshak/analyst/content_quality.py`, restructure `is_quality_content` so the word list is computed once, up front:

- Delete the character check at line 40.
- Move the word regex above the length check and compute `words` once.
- Single length gate: `len(words) < settings.content_min_words` returns `(False, "too_short")`.
- Delete the separate `len(words) < 5` check that returns `"few_words"`.
  Two thresholds on one dimension violates the one-setting-one-purpose rule.
- Leave `unique_ratio` and `punctuation` unchanged.
  Both are script-neutral ratios, and they are what actually catches navigation menus.
- Update the docstring's gate list at line 27.

In `services/analyst/anveshak/analyst/settings.py`:

- Add `content_min_words: int = 12`.
- Delete `content_min_length`.
  Leaving it means a later operator tunes it and nothing happens, which the dead-variable-cleanup rule exists to prevent.

Threshold rationale: the smallest genuine corpus item carries 16 words, so 12 leaves headroom.
`"Hello world"` carries 2 words and still returns `too_short`, so the existing test contract holds.

Gate-string choice: keep `"too_short"` and drop `"few_words"`.
`too_short` is the string already in the worker logs and in most existing tests, so keeping it minimises churn.

### B. Wire the thresholds into configuration

`content_min_words`, `content_min_unique_word_ratio` and `content_max_punctuation_ratio` live in `settings.py` today but appear in neither `infra/compose.yml` nor `.env`.
They cannot be tuned without a code edit, which is a large part of why this went unnoticed.

Add all three to the analyst service `environment:` block, and to `.env.example` and `.env`.

### C. The same defect, second copy, in the scraper

`services/scraper/anveshak/scraper/clean.py:485` holds `_MIN_CLEAN_CHARS = 100`, used by `score_content_quality` at line 514 for an identical `too_short` verdict.
It is a bare module constant rather than a setting, so it violates rule 6 as well as being script-blind.

Same treatment: word-count based, threshold read from settings, wired into compose.

This defect did not bite the Replay, because the corpus import path runs through `services/social/anveshak/social/ingest.py`, which never sets `content_quality` at all.
That is why all six rejected items read `content_quality = 'good'` in the database while the analyst gate rejected them.
Two components hold two unrelated notions of "quality" with no shared vocabulary.
That is worth a CONTEXT.md entry, but it is not code in this change.

### D. Configurable RAG embed timeout

In `services/reporter/anveshak/reporter/settings.py`, add `rag_embed_timeout_s: int = 120` beside the existing `ollama_report_timeout_s: int = 300`.

In `services/reporter/anveshak/reporter/rag.py`, read the timeout from that setting.

In `infra/compose.yml`, add `RAG_EMBED_TIMEOUT_S` to the reporter `environment:` block beside `OLLAMA_REPORT_TIMEOUT_S`.

## Tests

`tests/unit/test_content_quality.py` has a `_default_settings` fixture at line 14 patching the three thresholds.
It needs `content_min_words = 12` in place of `content_min_length = 100`.

Existing assertions to re-verify: `test_short_text_rejected`, `test_empty_text_rejected`, `test_real_article_accepted`, `test_navigation_boilerplate_rejected`.
Empty and whitespace-only input must still return `too_short`, so the implementation has to guard an empty word list.

New cases:

1. Devanagari regression, using the six real strings above.
   A 16-word, 89-character Hindi sentence must pass.
   This is the test that would have caught the defect.
2. One case per script the regex covers: Arabic, Bengali, CJK.
   CJK is the interesting one, because the regex treats each ideograph as a single word, so a short CJK item may legitimately fail a 12-word floor.
   Pin whatever behaviour is chosen rather than discover it in production.
3. Invariant test, per the threshold-invariant pattern in AGENTS.md.
   Assert `content_min_words` sits below the smallest word count in the golden corpus, so a future tuning change that would silently eat real content fails the suite instead of shipping.
4. `rag.py` builds its client from the setting rather than a literal.

Nine call sites across `tests/unit/` patch `is_quality_content` with `return_value=(True, "passed")`.
Those keep working, because the signature does not change.
`tests/integration/test_error_paths.py:40` calls it for real on `""`, `"   "` and `"hi"`, all of which must still fail.

## Rollout

1. Implement A, B, C and D with tests, RED first on the Devanagari case.
2. `make test-unit`.
3. Rebuild and restart `analyse-worker`, `analyse-scheduler`, `report-worker`,
   `scrape-web-worker` and `scrape-web-scheduler`.
   Settings are read at process start.
   The two scraper services are a rebuild rather than a restart, because
   `clean.py` now imports `anveshak.text` and the SDK is installed as a wheel at
   image build time.
   Missing them gives an `ImportError` crash loop rather than a silent failure,
   so it announces itself, but it still has to be in the list.
4. Re-score the items the old gate has already condemned.
   `score_content_quality` writes a persisted verdict, so every item any
   previous run stamped `low_quality/too_short` keeps that verdict and stays
   excluded by Gate 9 even after the code is correct.
   `scripts/backfill_quality_and_titles.py` re-runs the gate over history and is
   the tool for this.
   Without this step the fix applies only to newly scraped content.
5. Re-run the Replay.
   The analysis queue is empty, so no drain wait is needed.
6. Verify: zero unembedded items, all nine Hindi items clustered, both reports
   generated, `stance` non-null.

Review per repo rules: code-reviewer and security-auditor in parallel, plus
llm-safety-reviewer for D, which touches the reporter's RAG path.

## Corrections found during implementation

Four things in the sections above were wrong, and are recorded here rather than
silently edited, because the reasoning is the useful part.

**The floor is 8, not 12.**
A word floor is not automatically script-neutral either.
Dravidian agglutination packs into one word what English spreads over three, so
a one-sentence Telugu item counts 8 words and a Tamil one 9, where the English
equivalent counts 15.
The calibration table above shows floors of 8, 10, 12 and 15 all drop zero
corpus items, so the floor belongs at the bottom of that range.

**The word counter needed every script, not the six the analyst had.**
Fix A as written moved the analyst's existing regex into shared code, and that
regex covered Latin, Cyrillic, Arabic, Devanagari, Bengali and CJK only.
Tamil, Telugu, Kannada, Malayalam, Gujarati, Gurmukhi, Odia and Sinhala counted
zero words, which would have been a worse bug than the one being fixed: the
character floor was at least script-blind in both directions, and fix C moves
the word floor into the scraper, where the verdict is persisted.
`tests/unit/test_word_counter.py` now pins one sentence per language in
`stance_supported_languages`.

**Nine items, not six.**
The table in Defect 1 lists the six items that carry phases 3 to 5.
Measured over the whole corpus, the 100-character gate rejects nine, all Hindi.

**Fix D needed two more things.**
`rag_embed_timeout_s` is the read budget only; a bare scalar would have applied
120 seconds to connect as well, so a dead analyst would hold a worker slot for
two minutes instead of failing in five seconds.
And 120 plus `ollama_report_timeout_s` of 540 is 660 against an ARQ
`job_timeout` of 600, so the literal ceiling in `WorkerSettings` had to become
derived or ARQ would cancel jobs whose own timeouts were both still in budget.

## Out of scope

The RSS boilerplate defect.
`services/scraper/anveshak/scraper/rss.py:306` fetches article bodies and stores Crawl4AI `raw_markdown` directly, never calling `clean_extracted_text`, so navigation menus, subscribe prompts and cookie banners land in `clean_text`.
`services/scraper/anveshak/scraper/clean.py:1` states the contract that this path breaks, and `services/scraper/anveshak/scraper/jobs.py:31` honours it.
Measured contamination: 737 of 745 Hindustan Times Education items, 640 of 645 Indian Express Education items, against 0 for feeds that carry full text and need no fetch.

It is real, and it is arguably why these quality gates were tuned so aggressively in the first place, but it carries its own test surface and belongs in its own change.

Also out of scope: rejecting content on a per-script character budget instead of words.
Words are the better unit and the calibration supports it.
A per-script character table would be more machinery for no gain.
