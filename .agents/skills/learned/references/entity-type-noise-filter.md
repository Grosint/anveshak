# Entity Type Noise Filter for Report Tables

## Pattern
When displaying extracted entities in reports/dashboards, exclude noisy spaCy entity types that add no intelligence value. Also raise confidence threshold from 0.6 to 0.75.

## Exclude list
```sql
AND ee.entity_type NOT IN (
    'CARDINAL',   -- "1", "Two", "4" — numeric noise
    'ORDINAL',    -- "first", "second" — ordinal noise
    'QUANTITY',   -- "100 km", "5 kg" — measurement noise
    'DATE',       -- "1999", "2024", "Monday" — temporal noise
    'TIME',       -- "3 PM", "morning" — time noise
    'PERCENT',    -- "50%", "two-thirds" — percentage noise
    'MONEY'       -- "$100", "₹500" — monetary noise (masked as #####)
)
AND ee.confidence >= 0.75
```

## Keep list (intelligence-relevant)
GPE (countries/cities), ORG, PERSON, NORP (nationalities/groups), FAC (facilities), LOC (natural features), EVENT, PRODUCT, LAW, LANGUAGE.

## Why 0.75 not 0.6
At 0.6, spaCy misclassifications leak through ("EXIF" as ORG, "Malayalam" as ORG). At 0.75, most noise is filtered. True positives (Sabarimala=GPE, Kerala Special Branch=ORG) have confidence 0.85+.

## Caveat
This does NOT fix spaCy labeling errors (e.g., "EXIF" confidently labeled ORG at 0.9). For that, need an entity blacklist or model fine-tuning.
