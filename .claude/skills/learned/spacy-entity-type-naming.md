# spaCy Entity Type Names vs Common English Names

## Pattern
spaCy NER uses abbreviated entity type labels that differ from common English names.
When writing SQL or code that filters by entity type, use the spaCy label, not the
English word.

## Key mismatches
| spaCy label | Common name | Notes |
|-------------|-------------|-------|
| `FAC`       | FACILITY    | Buildings, airports, highways, bridges |
| `GPE`       | Geo-Political Entity | Countries, cities, states |
| `LOC`       | Location    | Non-GPE locations (mountain ranges, water bodies) |
| `NORP`      | Nationality/Religious/Political group | |
| `ORG`       | Organization | Correct — same label |
| `PERSON`    | Person      | Correct — same label |

## Context
SQL queries in `intelligence.py` used `'FACILITY'` instead of `'FAC'`, causing
zero matches despite 2712 FAC entities in the database. Co-occurrence graph showed
no facility relationships. Location map also affected.

## Rule
Always check `extracted_entities` table for actual stored values before writing
entity type filters:
```sql
SELECT entity_type, COUNT(*) FROM extracted_entities GROUP BY entity_type;
```

Never assume the English word — use the spaCy abbreviation.
