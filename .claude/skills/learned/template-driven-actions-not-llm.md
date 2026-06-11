# Pattern: Template-Driven Actions, Not LLM-Generated

## When to load: generating actionable recommendations in reports

---

## Problem

Recommended actions in intelligence reports (freeze accounts, request CDR,
file FIR) are high-stakes. LLM-generated actions risk:

1. Citing wrong legal sections (PMLA vs NDPS)
2. Recommending inapplicable procedures (CDR for crypto wallet)
3. Missing critical steps (freezing before evidence preservation)
4. Hallucinating legal provisions that don't exist

---

## The Pattern

Map each scam template to a curated, human-reviewed action list:

```python
_TEMPLATE_ACTIONS: dict[str, list[str]] = {
    "mule_recruitment": [
        "Freeze identified bank accounts and UPI IDs under PMLA Section 17",
        "Request CDR for associated phone numbers",
        "File STR with FIU-IND",
    ],
    "drug_sale": [
        "Request CDR and IP logs for identified phone numbers",
        "Coordinate with NCB for controlled delivery",
        "File case under NDPS Act Sections 20, 22, 25",
    ],
}
```

Then deterministically assemble from matched templates:

```python
def build_recommended_actions(template_matches: list[dict]) -> list[str]:
    actions = []
    seen = set()  # dedup across templates
    for match in template_matches:
        for action in _TEMPLATE_ACTIONS.get(match["template_name"], []):
            if action not in seen:
                seen.add(action)
                actions.append(action)
    return actions
```

---

## Why This Works

- Actions are reviewed by domain experts once, applied consistently forever
- Legal section references are exact (not hallucinated)
- Deterministic — same templates always produce same actions
- Deduplication handles overlapping templates (mule + crypto both mention PMLA)
- Template legal_sections field provides additional context per match
- Empty matches → empty actions list (graceful, no crash)

---

## When LLM Actions ARE Appropriate

- Generic strategic recommendations ("monitor this topic", "increase collection")
- These stay in the LLM-generated `recommendations` field
- Template-driven actions go in a SEPARATE "Recommended Actions" section

---

## Implementation reference
- `services/reporter/anveshak/reporter/rag.py` — `_TEMPLATE_ACTIONS` dict, `build_recommended_actions()`
- 11 built-in templates covered: mule, investment_fraud, maas, digital_arrest,
  job_fraud, pump_and_dump, fake_research_report, drug_sale,
  drug_delivery_recruitment, fake_sim_sale, crypto_cashout
