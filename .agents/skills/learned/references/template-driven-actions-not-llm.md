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

Map each scam template to a curated, human-reviewed action list, keyed by the
audience the report is addressed to, in a versioned file the customer owns
(`infra/configs/audiences/report_actions.yaml`, issue #57, ADR 0006):

```yaml
audiences:
  - id: prosecution
    actions_heading: Recommended Actions
    legal_provisions: own
    templates:
      mule_recruitment:
        - Freeze identified bank accounts and UPI IDs under PMLA Section 17
        - Request CDR (Call Detail Records) for associated phone numbers
        - File STR (Suspicious Transaction Report) with FIU-IND
  - id: advisory
    actions_heading: Assessment Priorities
    legal_provisions: attributed
    templates:
      mule_recruitment:
        - Map the recruitment network behind the identified accounts
        - Assess whether the recruitment is directed from outside the country
        - Refer the identified accounts to the service that can act on them
```

Then deterministically assemble from matched templates, for that audience:

```python
def build_recommended_actions(template_matches, audience=DEFAULT_AUDIENCE) -> list[str]:
    resolved = concrete_audience(audience)   # None means "no audience applies"
    if resolved is None:
        log.warning("reporter.actions_skipped", reason="...")
        return []
    actions, seen = [], set()                # dedup across overlapping templates
    for match in template_matches:
        for action in resolved.template_actions.get(match["template_name"], ()):
            ...
```

---

## Why This Works

- The same evidence frames two ways: a case file for a service that prosecutes,
  an assessment for one that does not. An FIR instruction to an intelligence
  consumer is mis-framed in the first line an officer reads
- Adding an audience is a file change, not a code change
- No fallback. An unknown audience, or an audience with no set for a matched
  template, yields NO actions and logs why. A silently borrowed prosecution
  step is the error this pattern exists to prevent
- Legal provisions appear as the reader's own only for `legal_provisions: own`;
  `attributed` marks them as another agency's, `omitted` drops them
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
- Template-driven actions go in a SEPARATE section, headed by whatever the
  audience calls it ("Recommended Actions", "Assessment Priorities")

---

## Implementation reference
- `infra/configs/audiences/report_actions.yaml` — the action sets, per audience
- `services/reporter/anveshak/reporter/audience.py` — loader, `resolve_audience()`
- `services/reporter/anveshak/reporter/rag.py` — `build_recommended_actions()`
- `organizations.report_audience` — which audience a deployment's reports are for
- 11 built-in templates covered: mule, investment_fraud, maas, digital_arrest,
  job_fraud, pump_and_dump, fake_research_report, drug_sale,
  drug_delivery_recruitment, fake_sim_sale, crypto_cashout
