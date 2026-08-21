# Trust Ladder: Each Customer Earns Access to Next Data Tier

## Pattern
Engine capabilities are gated by DATA ACCESS, not technology. Each deployment
earns trust that unlocks the next data tier.

```
Level 0: Public internet (anyone can scrape) → Engine A + C
Level 1: Public registries (MCA, DGCA, GeM) → Engine B
Level 2: Government feeds (I4C, CFCFRMS) → enriched Engine C
Level 3: Financial feeds (NPCI, FIU, RBI) → Engine E
Level 4: Classified feeds (NATGRID, telco CDR) → full platform
```

## When to apply
- When planning what to build next: ask "do we have data access?" not "can we build it?"
- When pricing: the moat is data access, not code
- When someone says "build Engine E (financial)" — ask "does NPCI give us data?"

## Why
- SEBI deployment → SEBI introduces you to NPCI → NPCI data enables financial intelligence
- Navy deployment → proves maritime capability → NATGRID conversation becomes real
- Technology without data access = demo. Technology with data access = product.

## Anti-pattern
Building Engine E (financial transaction tracking) before having NPCI/FIU data access.
The engine is useless without the data. Earn access first through trust, then build.
