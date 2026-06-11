Run the full demo arc and verify each step passes.

This command validates that Anveshak is ready for demos across all target agencies:
iDEX ADITI 4.0 PS-18 (original), plus Engine C demos for Police Cyber, SEBI, NCB, and MEA.

Prerequisites: docker compose up, seed_demo data loaded (make seed-demo).

---

## Part A: Core Platform (Original 8-Step iDEX Demo)

1. POST /api/v1/topics — create topic "Chinese naval activity Andaman Sea" — assert 201 with topic_id
2. GET /api/v1/topics/{topic_id}/content — assert >= 3 content_items (from seed data)
3. GET /api/v1/sources — assert all seeded sources have credibility_score assigned (not null)
4. GET /api/v1/topics/{topic_id}/entities — assert >= 1 extracted entity
5. POST /api/v1/vision/analyse — upload tests/fixtures/demo_image.jpg — assert deepfake_score is non-null float
6. GET /api/v1/topics/{topic_id}/clusters — assert >= 1 narrative cluster
7. POST /api/v1/reports — generate intelligence_brief for topic — poll until status=complete (timeout 120s)
8. GET /api/v1/reports/{report_id}/geojson — assert >= 1 feature in FeatureCollection
9. GET /api/v1/reports/{report_id}/pdf — assert 200 and Content-Type: application/pdf

---

## Part B: Engine C — Identifier Intelligence

### B1. Migration & Schema

10. Query pg: SELECT count(*) FROM scam_templates WHERE is_builtin = true — assert = 11
11. Query pg: SELECT column_name FROM information_schema.columns WHERE table_name = 'topics' AND column_name = 'identifier_signal_threshold' — assert exists
12. Query pg: SELECT count(*) FROM information_schema.tables WHERE table_name IN ('identifier_clusters', 'identifier_cluster_items', 'topic_templates') — assert = 3

### B2. Identifier Extraction

Use a topic with seeded content containing identifiers (phone numbers, UPI IDs, etc.).

13. GET /api/v1/topics/{topic_id}/entities — filter by entity_type IN ('PHONE_IN', 'UPI', 'EMAIL', 'CRYPTO_BTC', 'CRYPTO_ETH', 'CRYPTO_TRC20', 'TELEGRAM_HANDLE', 'INSTAGRAM_HANDLE', 'URL_DOMAIN', 'GSTIN') — assert >= 1 identifier-type entity extracted
14. GET /api/v1/identifiers/top?topic_id={topic_id}&limit=5 — assert 200, response contains >= 1 identifier with source_count >= 1

### B3. Scam Template Matching

15. GET /api/v1/templates — assert 200, response contains >= 11 built-in templates
16. GET /api/v1/topics/{topic_id}/content — check at least 1 content_item has labels.scam_template != null — assert template name is one of the 11 built-in templates
17. Check labels.template_confidence is a float between 0.0 and 1.0

### B4. Identifier Clustering

18. GET /api/v1/identifiers/clusters?topic_id={topic_id} — assert >= 1 identifier cluster exists
19. For the top cluster: assert source_count >= 2 (same identifier in 2+ sources)
20. GET /api/v1/identifiers/clusters/{cluster_id} — assert response contains content_item_ids list and identifier_value

### B5. New Signal Types

21. GET /api/v1/signals?topic_id={topic_id} — check for signal_type = 'identifier_convergence' — assert >= 1 exists OR assert signal engine checked (if threshold not met, that's ok — verify query runs without error)
22. GET /api/v1/signals?topic_id={topic_id} — check for signal_type = 'scam_template_match' — assert >= 1 exists OR assert signal engine checked without error

### B6. Identifier Search API

23. GET /api/v1/identifiers/search?q={known_phone_from_seed} — assert 200, returns matching content items
24. GET /api/v1/identifiers/export?topic_id={topic_id}&format=csv — assert 200, Content-Type contains csv, response body is non-empty

### B7. Tipline Ingestion

25. POST /api/v1/tipline/ingest with valid API key and body {"text": "Fraud alert: call +91-9876543210 for easy money, send to fraud@paytm", "topic_id": "{topic_id}"} — assert 201
26. Wait 10s for pipeline processing, then GET /api/v1/identifiers/search?q=9876543210 — assert the tipline content item appears with PHONE_IN extracted

---

## Part C: Agency-Specific Scenarios

Each scenario uses a dedicated demo topic. If seed data for the topic doesn't exist, skip with SKIP (not FAIL).

### C1. MEA Demo — Foreign Media Monitoring

27. Verify topic "MEA Beijing Demo" exists (or similar MEA topic from seed) — if not seeded, SKIP C1
28. GET content for MEA topic — assert >= 3 content_items with language != 'en' (multilingual content present)
29. Assert >= 1 content_item has translated_text != null (NLLB translation ran)
30. GET clusters for MEA topic — assert >= 1 narrative cluster (coordinated narrative detected)
31. GET signals for MEA topic — assert >= 1 multi_source_convergence signal
32. POST report for MEA topic — assert report generates successfully with geojson

### C2. Police Cyber Fraud Demo — Mule Account Detection

33. Verify topic "Cyber Fraud Demo" exists — if not seeded, SKIP C2
34. GET identifiers/top for cyber topic — assert PHONE_IN and UPI types present in top identifiers
35. GET content — assert >= 1 content_item with labels.scam_template = 'mule_recruitment' OR 'maas' OR 'investment_fraud'
36. GET identifiers/clusters — assert >= 1 cluster with source_count >= 2 (same actor across channels)
37. GET signals — assert >= 1 signal with signal_type = 'identifier_convergence' OR 'scam_template_match'
38. POST report — assert report contains "Identified Indicators" section (check content_md for the string)

### C3. SEBI Demo — Market Manipulation Detection

39. Verify topic "SEBI Surveillance Demo" exists — if not seeded, SKIP C3
40. GET identifiers/top — assert TELEGRAM_HANDLE type present (finfluencer handles extracted)
41. GET content — assert >= 1 content_item with labels.scam_template = 'pump_and_dump' OR 'fake_research_report'
42. GET clusters — assert >= 1 narrative cluster (coordinated stock pushing detected)
43. GET signals — assert >= 1 signal of any type for this topic

### C4. NCB Narco Demo — Drug Network Detection

44. Verify topic "NCB Intelligence Demo" exists — if not seeded, SKIP C4
45. GET identifiers/top — assert PHONE_IN or CRYPTO_BTC or TELEGRAM_HANDLE present
46. GET content — assert >= 1 content_item with labels.scam_template = 'drug_sale' OR 'drug_delivery_recruitment'
47. GET identifiers/clusters — assert >= 1 cluster (dealer operating across channels)

---

## Part D: Cross-Cutting Checks

48. GET /api/v1/identifiers/search with org A credentials, then org B credentials — assert results are org-isolated (no cross-org leakage)
49. POST /api/v1/tipline/ingest without API key — assert 401/403 (auth enforced)
50. GET /health/ready — assert 200 (system healthy after all checks)

---

## Reporting

Report PASS / FAIL / SKIP per step with response times.

Summary:
- Part A: X/9 PASS
- Part B: X/17 PASS
- Part C: X/21 PASS (Y SKIP if demo data not seeded)
- Part D: X/3 PASS

Final verdict:
- GO: All parts A + B pass, Part C has 0 FAIL (SKIP is ok)
- CONDITIONAL GO: Part A passes, Part B has <= 2 FAIL (non-critical)
- NO-GO: Any Part A failure OR Part B has >= 3 FAIL
