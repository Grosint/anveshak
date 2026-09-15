# Language pack implementation plan

Implements [ADR 0007](adr/0007-language-packs.md).

The embedding model, the models that read the same text, the language lists and the similarity thresholds calibrated against that embedding model become one versioned artifact, selected per deployment.

Vocabulary is in [CONTEXT.md](../CONTEXT.md).
Threshold history is recorded in [tuning_history.md](tuning_history.md).

---

## Architecture

### A language pack is a file, not a set of environment variables

One YAML file under `infra/configs/language_packs/`, following the convention already used by `infra/configs/taxonomies/concern.yaml` and `infra/configs/credibility/source_rubric.yaml`.

The grouping is the point.
An embedding model and the five similarity thresholds calibrated against it cannot be varied independently without silent breakage, so they live in one file that is chosen as a unit.

### The loader follows the pair pattern already in the SDK

`concern_settings.py` holds the path and `concern.py` parses and validates the file.
`source_rubric_settings.py` and `source_rubric.py` do the same.
Language packs add `sdk/anveshak/language_pack_settings.py` and `sdk/anveshak/language_pack.py`.

They live in the SDK rather than in the analyst service so that `scripts/verify_language_pack.py` and `scripts/migrate_language_pack.py` can import them without depending on a service package.

### Only the analyst embeds

`encode_text` and `embedding_model` appear in `analyst/embeddings.py`, `jobs.py`, `relevance.py`, `backfill.py`, `scheduler.py`, `download_models.py` and `settings.py`.
The API and the reporter do not embed.
The blast radius is one service plus two scripts.

### Translation moves off the critical path but is not removed

Embedding no longer depends on translation, because a multilingual embedding model reads the source language directly.

Translation is still required by four consumers, all of which are enrichment rather than evidence:

| consumer | location | why it still wants English |
|----------|----------|----------------------------|
| NER | `jobs.py:251-253` | `en_core_web_md` is the only spaCy model loaded |
| sentiment | `jobs.py:277` | English lexicon |
| keyword extraction | `jobs.py:278` | called with `language="en"` |
| analyst display | reporter, frontend | a human reads the text |

Each of those can fail without losing the item, once embedding does not depend on them.
That is the fail-open rule applied to the step that was previously the sole blocker.

### A pack is deployment-scoped

`content_items.embedding` is `vector(384)` with one shared HNSW index, and the dimension is DDL.
Two organisations on different packs inside one database would write incomparable vectors into one column.

This is the one place in the platform where `org_id` is not the isolation boundary, which is why it is stated in the ADR rather than left to be inferred.

### Everything routes by language except the embedding model

NER and translation are per-item operations.
Each reads one item and emits that item's output, and two items' outputs never have to be comparable, so a pack may name a different model per source language.

An embedding is relational.
Its only use is `cosine(a, b)`, so two embedding models mean two coordinate systems and a cross-model similarity is noise.
Both candidate models are 768 dimensions, so the column accepts either and nothing raises; the symptom is that Hindi content quietly stops clustering with the English press covering the same story.

One deployment, one embedding model.
An Indian-languages deployment takes `l3cube-pune/indic-sentence-similarity-sbert`, which covers ten Indian languages plus English.
A deployment needing Chinese, Arabic or Russian takes `intfloat/multilingual-e5-base`.
Neither can have both.

### Model residency is a budget, not an afterthought

The analyst worker runs under `mem_limit: 6g`.
Resident models are a fixed cost paid once per worker process, and every concurrent job adds its own inference activations on top, which is what `analyst_max_jobs` exists to bound.

Approximate fp32 footprints of what a pack can name:

| model | size |
|-------|------|
| `textdetox/xlmr-large-toxicity-classifier` | ~2.2 GB |
| `facebook/nllb-200-distilled-600M` | ~2.4 GB |
| `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` | ~1.1 GB |
| `intfloat/multilingual-e5-base` | ~1.1 GB |
| `ai4bharat/IndicNER` | ~0.7 GB |
| `ai4bharat/indictrans2-indic-en-dist-200M` | ~0.8 GB |
| `en_core_web_md` | ~40 MB |
| `all-MiniLM-L6-v2` | ~90 MB |

The current set already sits near the limit before anything is added.
Swapping NLLB-600M for IndicTrans2-200M frees roughly 1.6 GB, and that is what pays for IndicNER and a larger embedding model rather than new headroom appearing from nowhere.

Each pack therefore declares its own residency budget, and startup refuses a pack whose declared total exceeds the container limit.
An OOM mid-job restarts the container and loses the chained work the job had not yet enqueued, so this is a refusal at boot rather than a number discovered in production.

---

## The two initial packs

### `multilingual.yaml`

For deployments working foreign-language sources alongside Indian ones.

```yaml
name: multilingual
version: 1

embedding:
  model: intfloat/multilingual-e5-base
  dimensions: 768
  query_prefix: "query: "
  passage_prefix: "passage: "

ner:
  model: Davlan/xlm-roberta-base-ner-hrl

translation:
  model: facebook/nllb-200-distilled-600M
  timeout_s: 60
  source_codes:
    hi: hin_Deva
    mr: mar_Deva
    gu: guj_Gujr
    kn: kan_Knda
    pa: pan_Guru
    bn: ben_Beng
    ta: tam_Taml
    te: tel_Telu
    ml: mal_Mlym
    or: ory_Orya
    ur: urd_Arab
    zh: zho_Hans
    ar: arb_Arab
    ru: rus_Cyrl

stance:
  model: MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7
  hostility_model: textdetox/xlmr-large-toxicity-classifier
  supported_languages: [en, hi, bn, ta, te, mr, gu, kn, ml, pa, ur, ne, si, ar, fr, de, es, ru, zh, tr]

# Calibrated against this embedding model. Never copied between packs.
thresholds:
  clustering_similarity: null   # set by Phase 4
  cluster_assign: null
  near_duplicate: null
  cross_topic: null
  backfill: null
```

### `indic.yaml`

For deployments working Indian-language sources only.

Same keys, with `l3cube-pune/indic-sentence-similarity-sbert` for embedding, `ai4bharat/IndicNER` for NER, the Indian-script subset of the source code table, and its own calibrated thresholds.

Note that `e5` models require the `query:` and `passage:` prefixes and `indic-sentence-similarity-sbert` does not.
The prefix fields are therefore optional and default to the empty string, and `encode_text` applies whatever the pack declares.

---

## Selection

One environment variable, in the shape of `concern_taxonomy_path`:

```
LANGUAGE_PACK_PATH=/workspace/infra/configs/language_packs/multilingual.yaml
```

Set in `.env` per deployment, forwarded in the analyst `environment:` block, and included in the startup preflight extraction so a missing value blocks `make up` rather than defaulting.

---

## Schema changes

Four columns carry embeddings today, all `vector(384)`:

```
content_items.embedding
narrative_clusters.embedding_centroid
scam_templates.reference_embedding
trackers.centroid
```

One index:

```
idx_content_items_embedding  USING hnsw (embedding vector_cosine_ops) WITH (m='16', ef_construction='64')
```

A pack whose dimensions differ from the current column requires an `ALTER COLUMN ... TYPE vector(N)` on all four, and a drop and rebuild of the index.
This is carried by `scripts/migrate_language_pack.py` rather than by an Alembic revision, because the work is a data rewrite whose duration depends on corpus size, and because it must be runnable against an existing deployment as an operator action.

Alembic revision 010 records the column type for a fresh deployment.

---

## Phases

Phases 1 to 3 are behaviour-preserving on the current pack.
Phase 4 is the cutover.
Phases 5 and 6 remove the remaining dependencies on English input and can follow at any later point.

Phase 3 is independent of everything else here and is deployable on its own.
It is the fix for the failure measured on 2026-09-14, and it does not require the pack, the ADR or any migration.

### Phase 0 - Decisions of record

ADR 0007 written and accepted.
This plan committed.

### Phase 1 - The pack, loaded but not yet authoritative

- `infra/configs/language_packs/multilingual.yaml` and `indic.yaml`
- `sdk/anveshak/language_pack_settings.py`, `sdk/anveshak/language_pack.py`
- The parsed pack is a Pydantic model, so it needs `labels: Labels` or an `EXEMPT_MODELS` entry in `scripts/verify_labels.py` carrying a reason.
  Match whichever `concern.py` and `source_rubric.py` chose.
- `scripts/verify_language_pack.py` and a `make verify-language-pack` target, asserting that every pack in the directory declares dimensions matching the model it names
- A third pack file pinning the current `all-MiniLM-L6-v2` at 384 dimensions with today's threshold values, so Phase 2 has something to prove equivalence against

Exit: `make verify-language-pack` passes for all three packs.
No service reads a pack yet.

### Phase 2 - Analyst reads the pack

- `settings.py` stops declaring `embedding_model`, `embedding_dimensions`, `spacy_en_model`, `stance_model`, `hostility_model`, `stance_supported_languages`, `translation_model` and the five thresholds
- Every reader takes them from the loaded pack
- `encode_text` gains prefix support
- `translation.py` takes its source code table from the pack rather than the module-level `_NLLB_SRC_CODES`
- `download_models.py` downloads what the pack names
- Startup preflight asserts the three-way dimension agreement and raises on mismatch
- The old variables are deleted from `compose.yml` and `.env.example`

Exit: deployment runs on the `all-MiniLM-L6-v2` pack with identical behaviour.
`make test-unit`, `make test-integration` and `benchmark/mobilization.py` all match their pre-change results.

### Phase 3 - Translation stops being able to lose an item

Independent of the pack work and deployable on its own.
This is the fix for the failure measured on 2026-09-14.

- `translate_to_english` gains an inner timeout from `pack.translation.timeout_s`, well inside `job_timeout`
- A timeout returns `None` and routes into the existing `translation_failed_fallback` branch at `jobs.py:236`, so the item is still embedded
- `analyse_content` no longer retries a `TimeoutError`
- Every `analyse_content` enqueue passes `_job_id=content_item_id`, so the scraper, the orphan sweep and the demo scripts collapse to one job per item
- The orphan sweep gains a give-up count, so an item that can never succeed stops being swept forever
- A queue depth metric and an alert rule, because the observed failure was silent growth to 3873 jobs with nothing reporting it

Exit: a forced translation timeout leaves a row with an embedding, one job, and one warning.

### Phase 4 - Cutover to a multilingual pack

Per deployment, operator-run, guarded.

- `scripts/migrate_language_pack.py` with `ANVESHAK_ALLOW_EMBEDDING_MIGRATION=1`
- Calibrate the five thresholds for the target pack and write them into the pack file
- Decide, explicitly and per deployment, whether to re-cluster after re-embedding
- Record model, thresholds and benchmark deltas in `tuning_history.md`

Exit: `benchmark/mobilization.py` on the new pack is recorded and understood, whether it improved or not.

### Phase 5 - NER routing, and a canonical label vocabulary

Translation currently carries NER as well as human reading.
Hindi is translated and spaCy runs on the English, so Indic content gets the full spaCy label set computed over a translation.
Routing NER to a source-language model trades label coverage for name fidelity, and that trade has to be made deliberately.

`nlp.py:129` writes `ent.label_` straight through, unmapped, and two consumers read those strings by exact match:

```
geocoding_backfill.py:22   entity_type IN ('GPE', 'LOC', 'FAC')
labeller.py:51,131         entity_type IN ('GPE', 'ORG', 'PERSON', 'EVENT')
```

`ai4bharat/IndicNER` emits `PER`, `ORG` and `LOC`.
`PER` against a filter reading `PERSON` matches nothing and raises nothing, which is the same shape as the granularity mismatch recorded in `.agents/skills/learned/references/keyword-tag-granularity-mismatch.md`.

Work:

- A canonical label vocabulary in `nlp.py`, applied before any entity is written to `extracted_entities`.
  Every model's native labels map onto it: `PER` becomes `PERSON`, and where `LOC` sits relative to `GPE` is decided once and written down.
- NER routed by detected language, with the pack naming the model per language.
  spaCy stays for English, because an Indian-languages deployment still collects heavily from the English press.
- A decision, recorded per pack, on the types IndicNER does not emit.
  `GPE` drives the map and `EVENT` drives cluster labels, so the options are reduced coverage on Indic content stated honestly in the UI, or a hybrid that also runs spaCy over the translation when one exists and merges the results.
- A contract test asserting every label any configured model can emit is present in the canonical vocabulary, so adding a model cannot introduce an unmatched string silently.

Exit: an Indic item yields `PERSON` rather than `PER`, the map and cluster labels are unchanged for English, and the Indic coverage gap is recorded rather than discovered.

### Phase 6 - Retire the English-only enrichment

- Replace VADER, which is an English rule-based lexicon scoring near zero on Devanagari, an absence that currently reads as neutrality.
  Stance and hostility from #28 already measure this multilingually and mark `unsupported_language` honestly, so the likely outcome is deletion rather than replacement.
- YAKE keyword extraction is called with `language="en"` and uses English stopwords.
  Either give it per-language stopword lists or derive keywords from the multilingual embedding space.

Exit: no step in `analyse_content` assumes English input.

---

## Migration sequence

Carried by `scripts/migrate_language_pack.py`.
Each step prints a counter, in the manner of the demo seed script, so an operator can see which step is running.

1. Refuse unless `ANVESHAK_ALLOW_EMBEDDING_MIGRATION=1`
2. Refuse unless the target pack passes `verify_language_pack`
3. Stop ingest, or record that the operator accepted a collection window
4. `pg_dump --format=custom`, which is the rollback point
5. `DROP INDEX idx_content_items_embedding`
6. `ALTER COLUMN ... TYPE vector(N)` on all four columns, when dimensions change
7. Re-embed every `content_items` row with the new model
8. Recompute `narrative_clusters.embedding_centroid` as the mean of its re-embedded members, never by re-encoding the label
9. Re-embed `scam_templates.reference_embedding` and `trackers.centroid`
10. Recreate the HNSW index with the same `m` and `ef_construction`
11. Run `benchmark/mobilization.py` and print the delta against the recorded baseline
12. Print the re-cluster decision as an explicit prompt, and do not take it automatically

Rollback is `pg_restore` from step 4, or re-running the migration with the previous pack.
The previous model must stay pullable for the second option to exist, which matters on an air-gapped deployment.

---

## Settings inventory

Moving out of `settings.py` and into the pack:

| setting | current location | current value |
|---------|------------------|---------------|
| `embedding_model` | `settings.py:39` | `all-MiniLM-L6-v2` |
| `embedding_dimensions` | `settings.py:40` | 384 |
| `clustering_similarity_threshold` | `settings.py:64` | see file |
| `cluster_assign_threshold` | `settings.py:70` | 0.60 |
| `near_duplicate_similarity_threshold` | `settings.py:216` | 0.95 |
| `cross_topic_similarity_threshold` | `settings.py:244` | 0.85 |
| `backfill_similarity_threshold` | `settings.py:249` | 0.85 |
| `spacy_en_model` | `settings.py:12` | `en_core_web_md` |
| `stance_model` | `settings.py:82` | mDeBERTa xnli |
| `stance_supported_languages` | `settings.py:95` | 20 languages |
| `hostility_model` | `settings.py:118` | xlmr toxicity |
| `_NLLB_SRC_CODES` | `translation.py:35` | 10 languages |

New:

| setting | default |
|---------|---------|
| `language_pack_path` | `/workspace/infra/configs/language_packs/multilingual.yaml` |

To be deleted from `compose.yml` and `.env.example` in Phase 2: `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`, and any threshold variable now carried by the pack.

---

## Invariant tests, mandatory

```python
def test_every_pack_declares_its_models_real_dimensions():
    # Guards the silent case: two models, same dimension, incomparable spaces.
    for pack in load_all_packs():
        model = SentenceTransformer(pack.embedding.model)
        assert model.get_sentence_embedding_dimension() == pack.embedding.dimensions


def test_pack_dimensions_match_the_database_column():
    # The three-way assertion the analyst makes at startup.
    assert pack.embedding.dimensions == column_typmod("content_items", "embedding")


def test_no_threshold_survives_in_settings():
    # A threshold in two places is a threshold that can disagree with itself.
    for name in PACK_OWNED_THRESHOLDS:
        assert not hasattr(settings, name)


def test_no_dead_embedding_vars_in_compose():
    # Dead vars are silently ignored by pydantic, so tuning them looks correct
    # and does nothing.
    compose = read_compose()
    for var in ("EMBEDDING_MODEL", "EMBEDDING_DIMENSIONS"):
        assert var not in compose


def test_translation_timeout_is_inside_job_timeout():
    # A translation bounded only by job_timeout kills the job instead of
    # falling back. This is the 2026-09-14 failure.
    assert pack.translation.timeout_s < WorkerSettings.job_timeout


def test_pack_names_exactly_one_embedding_model():
    # Routing by language is correct for NER and translation and wrong for
    # embedding, because a vector only has meaning relative to other vectors.
    # ADR 0007 decision 4.
    assert isinstance(pack.embedding.model, str)
    assert not hasattr(pack.embedding, "routes")


def test_pack_residency_fits_the_container_limit():
    # An OOM mid-job restarts the container and loses chained work, so this is
    # refused at boot rather than discovered in production.
    assert pack.residency_bytes() < container_mem_limit()


def test_every_ner_label_is_in_the_canonical_vocabulary():
    # IndicNER emits PER where labeller.py filters PERSON. A string filter that
    # matches nothing returns an empty set, not an error.
    for model in pack.ner.models.values():
        for label in native_labels(model):
            assert canonical_label(label) in CANONICAL_ENTITY_TYPES


def test_stance_languages_are_translatable_or_declared_untranslated():
    # Marathi scored for stance but absent from the NLLB table is the gap this
    # pack exists to close.
    for lang in pack.stance.supported_languages:
        assert lang in pack.translation.source_codes or lang in pack.embedding_only_languages
```

---

## Test matrix

| Layer | What it proves | Marker |
|-------|----------------|--------|
| unit | pack parses, validates, rejects a dimension mismatch | `unit` |
| unit | timeout in translation returns `None` and does not raise | `unit` |
| unit | `analyse_content` writes an embedding when translation times out | `unit` |
| unit | duplicate `analyse_content` enqueues collapse under one `_job_id` | `unit` |
| integration | analyst boots on each pack and refuses a mismatched one | `integration` |
| integration | re-embed and centroid recompute leave clusters consistent | `integration` |
| contract | no pack-owned setting remains in `settings.py` or compose | `unit` |
| unit | every NER model's labels are in the canonical vocabulary | `unit` |
| unit | declared pack residency fits the container `mem_limit` | `unit` |
| benchmark | `benchmark/mobilization.py` per pack, recorded | n/a |

Tests must pass on CPU with the default pack.
Embedding fixtures must be L2-normalised, and the seeded-RNG calibration values in `.agents/skills/learned/references/test-embedding-realism.md` apply unchanged.

---

## Risk register

| Risk | Consequence | Mitigation |
|------|-------------|------------|
| Two models share a dimension and vectors are mixed | Silent mis-clustering, no error anywhere | Migration is all-or-nothing under a typed guard, plus the startup three-way assertion |
| Thresholds carried over uncalibrated | Dedup and convergence fire wrongly, still no error | Thresholds live inside the pack, and a pack with null thresholds fails `verify-language-pack` |
| `multilingual-e5-base` is three times the encode cost | Throughput falls further on a worker already behind | Phase 3 lands first and removes NLLB from the path, a far larger saving; sizing is a `hardware.md` decision |
| Re-cluster decision taken by default | Existing signals and candidate scores silently change meaning | Step 12 prompts and does not act |
| Air-gapped deployment cannot pull the new model | Migration strands mid-way | Step 2 verifies the model loads before step 5 drops anything |
| Pack chosen per organisation by mistake | Incomparable vectors in one column | Stated in ADR 0007, and there is no per-org code path to reach |
| `e5` prefixes omitted | Quality degrades quietly, no error | Prefixes are pack fields, and the benchmark gate is what catches the regression |
| Embedding model routed per language | Cross-language clustering silently stops, no error | ADR 0007 decision 4; there is no per-language code path for embedding, and the pack carries one model |
| `PER` written where a consumer filters `PERSON` | Entities vanish from cluster labels, no error | Canonical label vocabulary plus the contract test in Phase 5 |
| Pack residency exceeds `mem_limit` | Container OOMs mid-job and loses chained work | Declared residency budget, refused at startup |
