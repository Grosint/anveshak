# ADR 0007: The embedding model and the thresholds calibrated against it are one versioned language pack

- Status: Proposed
- Date: 2026-09-14
- Issue: not yet filed

## Context

Architectural rule 6 states that no model name, device string or ML parameter appears in service code, and that all of it comes from `settings.py` via environment variables.
The rule is followed.
`embedding_model` is a setting, `stance_model` is a setting, and `translation_model` is a setting.

The rule is not sufficient, for two reasons that only became visible under load.

### Translation sits on the embedding critical path

`settings.py:39` selects `all-MiniLM-L6-v2`.
That model has an English WordPiece vocabulary, so Devanagari tokenises into subword fragments that carry almost no meaning.
Content in an Indian language therefore has to be rendered into English before it can be embedded at all.

`jobs.py` does exactly that.
Step 2 translates, Step 4 embeds, and the text both operate on is `work_text`, which is the translation when one exists and the original otherwise.
Clustering, cluster assignment, near-duplicate detection, topic relevance and the novelty score behind candidate promotion all read the vector produced at Step 4.

NLLB-200-distilled-600M generates tokens autoregressively.
On the analyst worker, capped at four CPUs with `max_jobs=4` and `TORCH_NUM_THREADS=2`, four concurrent generations oversubscribe the container by a factor of two, and a longer article exceeds ARQ's `job_timeout` of 300 seconds.

The failure that follows is worse than slowness.
`jobs.py:228` wraps the call in `asyncio.to_thread` with no timeout of its own, so the only bound is the job timeout, and the job dies:

```
300.02s ! 04bc8a871dd24ed79268d13b45560ec3:analyse_content failed, TimeoutError:
    translated_text = await asyncio.to_thread(translate_to_english, clean_text, lang)
```

A fallback for exactly this case already exists twelve lines further down.
`jobs.py:236` logs `analyst.translation_failed_fallback` and embeds the original text when translation returns `None`.
A timeout never reaches it, because a timeout raises rather than returning `None`.
The item ends the job with no embedding, no entities and no relevance score.

Because `embedding IS NULL` is also the orphan sweep's selection criterion, the sweep re-enqueues those same items, and `max_tries=3` at `jobs.py:757` retries each one.
A single Hindi article can therefore consume 900 seconds of worker capacity and still produce nothing.

Measured on the development deployment on 2026-09-14: 766 items with no embedding, of which 333 are Hindi, against a queue of 3873 jobs covering 848 distinct content ids, a duplication factor of roughly 4.5.

### The language lists already disagree with each other

The stance and hostility work took the opposite approach and was right to.
`stance.py:13` records the reasoning: both models are multilingual so content is read in its own language rather than through a translation, and content the models handle poorly is marked `unsupported_language` rather than silently scored.

That leaves two language lists in the same service that do not match.

`translation.py:35` covers ten languages, of which seven are Indian: Hindi, Urdu, Bengali, Telugu, Tamil, Odia and Malayalam.
`settings.py:95` covers twenty, of which twelve are Indian, adding Marathi, Gujarati, Kannada, Punjabi, Nepali and Sinhala.

A Marathi item today is scored for stance and hostility correctly, is refused translation because `mr` is absent from `_NLLB_SRC_CODES`, and then reaches `jobs.py:251` where `nlp_lang` becomes `mr`, `is_model_loaded("mr")` returns false, and NER is skipped entirely.
Its embedding is computed by an English-only model over Devanagari.
Nothing in that sequence raises.

NLLB-200 supports all four missing languages.
They are absent from a dictionary, not from the model.

### Different deployments need different languages

Anveshak is deployed per agency, on premises, with no shared cloud tier.
An agency working foreign-language sources and an agency working only Indian-language sources do not want the same embedding model, and neither wants to carry the other's.

### Why a setting is not enough

An embedding vector is a coordinate in one model's space.
Coordinates from two models are not comparable, but they are both arrays of floats of the same length, so nothing rejects them.

Swapping `EMBEDDING_MODEL` between two 768-dimension models and restarting therefore produces no error at any layer.
The existing rows keep the old coordinates, the new rows take the new ones, and every comparison that crosses the boundary returns a plausible number that means nothing.
The five thresholds calibrated against the old model keep their values and keep being applied.

The model and the thresholds calibrated against it are one decision.
The current design lets them be changed independently, and a wrong combination is silent.

## Decision

The embedding model, the models that read the same text, the language lists and the similarity thresholds are one versioned artifact, selected per deployment.

1. **Embedding becomes multilingual, and translation leaves the critical path.**
   The default pack embeds with `intfloat/multilingual-e5-base`: 768 dimensions, an XLM-R backbone, and roughly one hundred languages including Bengali, Tamil, Telugu, Malayalam, Kannada, Punjabi and Odia, none of which `paraphrase-multilingual-MiniLM-L12-v2` covers.
   A single encoder forward pass replaces autoregressive generation, so the 300 second timeouts are removed rather than raised.

2. **A language pack is one YAML file** under `infra/configs/language_packs/`, following the existing `infra/configs` convention and loaded by the pair pattern already used by `concern_settings.py` and `source_rubric_settings.py`.
   It pins the embedding model and its dimensions, the NER model, the translation model and its source code table, the stance supported-language list, and the five similarity thresholds calibrated against that embedding model.

3. **The thresholds live in the pack and nowhere else.**
   `clustering_similarity`, `cluster_assign`, `near_duplicate`, `cross_topic` and `backfill` move out of `settings.py` and out of the compose environment block.
   The old variables are deleted rather than left defaulting, because a variable pydantic silently ignores looks like a working knob.

4. **One deployment, one embedding model. Never per organisation, and never per language.**
   Every other model in the pack may be routed by detected language, because NER and translation are per-item operations: each reads one item and emits that item's output, and two items' outputs never have to be comparable to each other.
   An embedding is not a per-item operation.
   A vector has no meaning alone; its only use is `cosine(a, b)`, and the capability being built is comparing a Hindi post to an English article about the same narrative.
   Two embedding models are two coordinate systems, so a similarity computed across them is noise.
   Both candidate models are 768 dimensions, so the column accepts either and nothing raises.
   The result is a clustering engine that silently stops grouping content across languages, which is the failure this ADR exists to prevent.
   `content_items.embedding` is a single `vector(N)` column with one shared HNSW index, and the dimension is DDL rather than configuration.
   This is stated explicitly because `org_id` isolation is first-class everywhere else in the platform, and because routing by language is correct for every other model in the pack, so both exceptions will otherwise be assumed away.
   Embedding every item twice into two columns is not a way around this: clustering still happens in exactly one space, so the second set of vectors is storage and compute that nothing reads.

5. **Startup refuses a mismatch.**
   The dimension declared by the pack, the dimension reported by the loaded model, and the column typmod in PostgreSQL must agree, and the analyst raises at startup when they do not.
   Deny by default, in the posture of `verify_labels.py`.
   Without it a mismatch appears as a per-row pgvector insert failure inside a worker, hours after the deployment that caused it.

6. **Changing pack is a migration, not a restart.**
   `scripts/migrate_language_pack.py` carries a typed guard in the manner of `replay-restore`, dumps first, drops the HNSW index, re-embeds all four vector columns, recomputes cluster centroids from their re-embedded members, rebuilds the index, and reports benchmark deltas.

7. **Translation stays, as enrichment.**
   It is still required for the analyst reading the text, and for NER, sentiment and keyword extraction until those consumers are multilingual.
   It runs on its own queue with its own timeout well inside `job_timeout`, and a failure routes into the existing `translation_failed_fallback` branch so the item is still embedded, still clustered and still visible.
   A timeout is not retried, because an operation that exhausted its budget on CPU will exhaust it again.

## Consequences

Translation stops being able to lose an item.
The pipeline reaches a valid embedded state without it, which is the fail-open rule applied to the step that was the sole blocker.

The four Indian languages that today receive stance scores but no translation and no NER stop being a silent gap, because the pack carries one language list rather than three that drift.

Every deployment pays a larger vector.
768 dimensions doubles the storage per row and enlarges the HNSW index, and `multilingual-e5-base` costs roughly three times `all-MiniLM-L6-v2` per encode on CPU.
That is a real cost and it is accepted, because it is paid once per item as a forward pass, against an NLLB generation measured in seconds to minutes.

Dimension count is not the reason for the choice.
`multilingual-e5-small` at 384 dimensions is a defensible pack in its own right and is expected to be one, for deployments where throughput matters more than headroom.
The pack mechanism exists so that comparison is a benchmark result rather than an argument.

The per-deployment choice this delivers is the point of the whole design.
A deployment working Indian languages and English takes `l3cube-pune/indic-sentence-similarity-sbert`, which is trained on ten Indian languages plus English and therefore clusters Indian-language content with the English press covering the same story.
A deployment that also needs Chinese, Arabic or Russian takes `intfloat/multilingual-e5-base` and accepts weaker Indian-language pairs in exchange for coverage.
Neither deployment can have both, and the benchmark per pack is what makes that a measured trade rather than a preference.

Adopting this on an existing deployment is a full re-embed and a decision about whether to re-cluster.
Clusters were formed by old-space distances, and signals, candidate scores and reports were derived from those clusters.
Reports remain valid as point-in-time artifacts under rule 4, but the cluster identifiers they cite may describe a different grouping afterwards.
That decision is taken per deployment and recorded, not defaulted.

Rule 6 is narrowed rather than weakened.
Model names still never appear in service code.
They now come from a file that also carries the numbers that are only correct for that model, because the two cannot be varied independently without silent breakage.

`benchmark/mobilization.py` becomes a per-pack gate.
A pack without a recorded benchmark run in `docs/tuning_history.md` is not a pack anyone should deploy.
