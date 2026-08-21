# Engine Layering: Sangrah → Engines → Products

## Pattern
Separate data collection (Sangrah) from analysis (Engines A/B/C/D) from packaging (Products).
Different buyers need different engine combinations on the same data:

```
Sangrah (collection — invisible infrastructure)
    │
    ├── Engine A: Narrative (NLP → embed → cluster → signal)
    ├── Engine B: Identity (entity resolution → graph → ownership)
    ├── Engine C: Indicator (regex extract → identifier cluster → template match)
    └── Engine D+: Future engines as data access is earned
    │
    ├── Anveshak = A + C       (police, MEA, SEBI)
    ├── Drishti  = A + B + C   (Navy, NIA, NSCS)
    └── Future   = any combo
```

## When to apply
- When a new use case (cyber fraud, narco, SEBI) seems to need a "new product"
- First check: can it be served by adding an engine to existing product?
- Only create a new product when the buyer is fundamentally different (classification level, infrastructure, budget tier)

## Why
- Engine C (identifiers) unlocked 4 markets without creating 4 products
- Sangrah extraction deferred because Anveshak's scraper already works — extract only when multi-product consumption is real
- Building the cathedral before selling bricks wastes runway

## Key rule
Don't extract Sangrah until you have 2+ products consuming from the same sources.
Don't build Engine B until someone asks for cross-domain identity resolution.
Build what generates revenue NOW, defer what's architecturally correct but premature.
