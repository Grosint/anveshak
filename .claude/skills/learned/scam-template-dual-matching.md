# Scam Template: Keyword + Embedding Dual Matching

## Pattern
Scam/fraud/info-op templates use TWO matching signals, take the max:

```python
keyword_score = keyword_hits / total_keywords  # lexical match
embedding_score = cosine_sim(content.embedding, template.reference_embedding)  # semantic
confidence = max(
    (0.6 * keyword_score + 0.4 * identifier_match),
    embedding_score
)
```

Reference embedding computed from 3-5 analyst-provided example messages (mean of embeddings).
Uses existing MiniLM-L6-v2 infrastructure — zero additional models.

## When to apply
- Building any content classification system without ML training data
- When keyword matching alone has too many false negatives (paraphrased content)
- When embedding-only matching has too many false positives (semantically similar but different intent)

## Why
- Keywords catch exact patterns ("bank account for sale")
- Embeddings catch paraphrased versions ("accounts ready for interested parties")
- Taking max() ensures either signal alone can trigger a match
- Reference embeddings from analyst examples = lightweight "training" without ML pipeline
- Works in Hindi/Urdu (post-translation) because matching runs on English text

## Source
Designed for Engine C scam template library. 11 built-in templates covering
fraud (mule, investment, digital arrest, job), narco (drug sale, delivery),
SEBI (pump-and-dump, fake research), and info ops (anti-India narratives).
Templates are universal across agencies — same mechanism, different keywords.
