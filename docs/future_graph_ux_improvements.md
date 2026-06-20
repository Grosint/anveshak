# Future: Intelligence Graph UX Improvements

Captured from graph debugging session (2026-06-17). Not yet implemented.

## 1. NER Entity Type Coloring

**Problem:** All NER entity nodes render as gray circles. spaCy returns correct types (PERSON, ORG, FAC) but `EntityGraph.tsx` only has Cytoscape style selectors for identifier types (PHONE_IN, UPI, etc.).

**Fix:** Add `NER_STYLES` map and Cytoscape selectors:
- PERSON → orange (`#f97316`)
- ORG → blue (`#3b82f6`)
- FAC → purple (`#8b5cf6`)

Update legend bar with PERSON/ORG/FAC entries.

**File:** `frontend/src/components/workspace/EntityGraph.tsx`

---

## 2. NER Noise Filtering

**Problem:** spaCy misclassifies common banking/crypto terms as ORG entities: "upi", "usdt", "rtgs", "fund", "funds", "official". Dirty text artifacts leak through: "gramin bank)" with parenthesis.

**Approaches (pick one or combine):**

### a. Document frequency cap (recommended)
Filter entities appearing in >30% of topic's content items. Generic terms appear everywhere; real entities are specific.
```sql
HAVING COUNT(DISTINCT e1.content_item_id) <= (SELECT COUNT(*) FROM content_items WHERE topic_id = $1) * 0.3
```

### b. Capitalization heuristic
Real ORG names are capitalized ("Reserve Bank of India"). Single lowercase words ("fund") are noise.
```sql
AND (e1.entity_text ~ '[A-Z]' OR LENGTH(e1.entity_text) > 6)
```

### c. Dirty text regex filter
Strip entities with parentheses, brackets, asterisks.
```sql
AND e1.entity_text !~ '[()\\[\\]*]'
```

### d. Hardcoded stopword list (fragile, NOT recommended)
Breaks if "UPI" is a legitimate org in another topic.

**Recommendation:** Combine (a) + (c). Document frequency cap handles unknown noise dynamically. Dirty text filter catches artifact leakage.

---

## 3. Entity Node Size

Current: `size: 28`. Increase to `size: 34` for readability.

---

## 4. Upstream NER Quality (longer term)

Rather than filtering at display time, improve NER quality at ingestion:
- Add domain-specific entity exclusion list to analyst pipeline
- Post-NER validation: reject entities matching known non-entity patterns
- Consider fine-tuning spaCy on financial crime corpus

**Trade-off:** Changes stored data, requires re-analysis of existing content. Display-level filtering is faster to ship.

---

## Related Files

- `frontend/src/components/workspace/EntityGraph.tsx` — graph component
- `services/api/anveshak/api/routes/intelligence.py` — `SQL_ENTITY_COOCCURRENCE`
- `services/analyst/anveshak/analyst/jobs.py` — NER extraction pipeline
