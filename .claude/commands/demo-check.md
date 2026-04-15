Run the full 8-step demo arc and verify each step passes.

This command validates that Anveshak is ready for the iDEX ADITI 4.0 PS-18 evaluation demo.

Prerequisites: docker compose up, seed_demo data loaded (make seed-demo).

Steps to verify:
1. POST /api/v1/topics — create topic "Chinese naval activity Andaman Sea" — assert 201 response with topic_id
2. GET /api/v1/topics/{topic_id}/content — assert >= 3 content_items (from seed data)
3. GET /api/v1/sources — assert all seeded sources have credibility_score assigned (not null)
4. GET /api/v1/topics/{topic_id}/entities — assert >= 1 extracted entity
5. POST /api/v1/vision/analyse — upload tests/fixtures/demo_image.jpg — assert deepfake_score is non-null float
6. GET /api/v1/topics/{topic_id}/clusters — assert >= 1 narrative cluster
7. POST /api/v1/reports — generate intelligence_brief for topic — poll until status=complete (timeout 120s)
8. GET /api/v1/reports/{report_id}/geojson — assert >= 1 feature in FeatureCollection
9. GET /api/v1/reports/{report_id}/pdf — assert 200 and Content-Type: application/pdf

Report PASS/FAIL per step with response times.
Final verdict: GO (all pass) or NO-GO (any fail).
