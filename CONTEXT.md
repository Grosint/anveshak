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
