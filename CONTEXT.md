# Anveshak — Domain Glossary

Terms used across the codebase and product. Canonical meanings only — no implementation details.

---

## Core Entities

**Topic** — A collection scope that defines what gets scraped and monitored. An analyst creates a topic to track a subject (e.g., "Kerala Cyber Fraud Ring"). Topics own sources, content items, clusters, signals, and reports. Topics are *not* cases — they are data collection boundaries.

**Source** — A feed, channel, or account that produces content. Global entity (an RSS feed is the same feed regardless of who monitors it). Linked to topics via `topic_sources`. Has credibility score and health status.

**Content Item** — A single scraped artifact: article, post, message, image. Always belongs to one source and one topic. Carries `content_hash` for dedup, `credibility_score_at_capture` for audit. The atomic unit of evidence.

**Narrative Cluster** — A group of content items about the same emerging story, detected via embedding similarity (Leiden). Has a label, independent source count (ISC), and growth rate. Clusters are topic-scoped.

**Signal** — An alert fired when a narrative cluster's independent source count crosses the topic's threshold. Signals have status: `new → acknowledged → dismissed`. The primary "pay attention" mechanism.

**Identifier** — A structured entity extracted from content: phone number, UPI ID, bank account, crypto wallet, Telegram handle, email, GSTIN, PAN, etc. Stored in `extracted_entities`. The primary cross-topic linkage point — same identifier in multiple topics indicates convergence.

**Case** — A long-running investigation tracked by an analyst. Can span multiple topics. Has status (`watching`, `active`, `concluded`) and priority (`critical`, `high`, `medium`, `low`). Previously called "Tracker" in engineering; renamed to match LEA vocabulary.

**Report** — An immutable point-in-time intelligence output. Once `generated_at` is set, never modified. Contains `source_snapshot` capturing credibility at generation time. Updated intelligence requires a new report.

---

## UX Concepts

**Provenance Chain** — The traceable lineage of any data point back to its origin. Every entity in the system must answer "why am I here?" The canonical chain is: `Identifier → Content Item(s) → Source(s) → Cluster → Topic`. Works bidirectionally.

**Intelligence View** — The default view when opening a topic workspace. Shows signals, narrative clusters, key identifiers, source health, and location pills — everything an analyst needs to answer "what's happening?" Single scrollable page, no tabs within it.

**Content View** — Full evidence feed for a topic. Infinite-scroll content items with filters (platform, language, sentiment, date range, credibility). Answers "show me the proof."

**Map View** — Full-screen MapLibre visualization of geographic data within a topic. Primary tool for LEA field operations. Not a widget — a first-class view.

**Provenance Panel** — A right-side panel that opens on clicking any entity. Shows the full provenance chain for that entity. Stack-based navigation: clicking an item inside the panel pushes a new view (with back button), allowing analysts to follow investigation trails.

**Location Pill** — A compact geographic indicator (e.g., `Kochi (12)`) shown on the Intelligence View. Clicking opens Map View. The count represents content items mentioning that location.

---

## Cross-Cutting Concepts

**Convergence** — When the same identifier appears in multiple topics, indicating a connection between seemingly unrelated investigations. Detected via cross-topic identifier search.

**Urgency** — The computed priority of a topic based on: unacknowledged signal count, new content in last 24h, and source health. Used to sort the Topics Dashboard so analysts see what needs attention first.

**ISC (Independent Source Count)** — Count of distinct sources (not platforms) contributing to a narrative cluster. Core metric for signal firing. Three RSS sources = ISC 3, not ISC 1.

**Severity** - A neutral magnitude indicator on a signal, computed from propagation facts alone (independent source count, item count, contributing account count), never from a judgement about content. Rendered alongside the arithmetic that produced it. A severity badge is a measurement, not an accusation. See ADR 0001.

---

## Narrative Detection

**Watch Space** - A Topic that collects across a whole domain of interest rather than one named subject. Technically an ordinary Topic (`is_watch_space = TRUE`) with broad keywords and many attached sources. Its keywords describe a domain and name no specific organisation, party, or individual. It is what gives narrative detection something to detect within.

**Candidate Topic** - A narrative cluster inside a Watch Space that crossed all four promotion gates and is proposed to the analyst for triage. Has status `pending`, `accepted`, or `dismissed`. Nothing is monitored until an analyst accepts. Accepting creates a child Topic linked back to the Watch Space via `parent_topic_id`.

**Promotion Gates** - The four independent conditions a cluster must all pass to become a Candidate Topic: independent source count, cluster size, novelty (distance from every existing Topic centroid), and persistence across clustering runs. Novelty prevents rediscovery of Topics the analyst already tracks. Persistence eliminates single transient spikes.

**Stance** - The direction of a content item toward its narrative cluster: `supporting`, `opposing`, or `neutral`. Scored after cluster assignment, because the target is the cluster label and that is unknown at ingest. Assessed in the content's own language where the model supports it; marked `unsupported_language` otherwise rather than silently scored.

**Hostility** - The intensity of a content item, 0.0 to 1.0, independent of stance. A furious supporting post and a calm opposing post differ in stance and in hostility, and no single sentiment score separates them. NULL on scoring error, never 0.0.

**Sentiment Timeline** - A chart of a narrative over publication time: supporting and opposing volume as separate series, with mean hostility overlaid on a secondary axis. Plots `published_at` and excludes items lacking it, reporting them as a footnote count.

**Manufactured Narrative** - A signal that fires when item count and contributing account count climb while independent source count stays flat. That is amplification rather than reporting. The signal reports that spread lacks independent sourcing. It never asserts that a narrative is false.

**Mobilization Signal** - A signal that fires when public content contains an explicit call for people to assemble, carrying the extracted date and place and the exact phrase that triggered it. Reports what was publicly said. Never predicts that an event will occur and carries no probability that one will.

**Actor View** - A view of the public content authored by a single handle within a Topic, reached from any handle in the Provenance Panel. A query, not a stored entity: no actor table and no persistent per-person record exists.

**Concern Category** - A behaviour-based or harm-based label from a versioned taxonomy the customer owns. Available to the analyst as a filter. Orders nothing, anywhere, and is never surfaced unprompted. See ADR 0001.
