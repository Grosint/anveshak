"""Entity MinHash fingerprinting for clustering boost.

Computes a MinHash signature from extracted entity texts at ingestion time.
At clustering time, MinHash similarity between items is blended into the
similarity matrix to help Leiden cluster articles that share entities but
have distant embeddings (e.g., a dark web post and a CERT-In advisory
both mentioning "AIIMS" + "Delhi").

The MinHash is stored as INTEGER[] in content_items.entity_minhash.
"""
from __future__ import annotations

from datasketch import MinHash

import numpy as np


def compute_entity_minhash(
    entity_texts: list[str],
    num_perm: int = 128,
) -> list[int]:
    """Compute MinHash signature from entity texts.

    Args:
        entity_texts: list of entity strings from NER
        num_perm: number of permutations (higher = more accurate, default 128)

    Returns:
        List of num_perm integers (the MinHash signature)
    """
    m = MinHash(num_perm=num_perm)
    for text in entity_texts:
        m.update(text.lower().strip().encode("utf-8"))
    return m.hashvalues.tolist()


def minhash_similarity_matrix(
    minhash_list: list[list[int] | None],
) -> np.ndarray:
    """Compute pairwise MinHash similarity matrix.

    Items with None minhash (no entities extracted) get similarity 0.0
    with all other items.

    Returns:
        N×N float64 matrix of Jaccard similarity estimates [0.0, 1.0]
    """
    n = len(minhash_list)
    sim = np.zeros((n, n), dtype=np.float64)

    # Convert to numpy arrays for fast comparison
    arrays = []
    for mh in minhash_list:
        if mh is not None:
            arrays.append(np.array(mh, dtype=np.int64))
        else:
            arrays.append(None)

    for i in range(n):
        if arrays[i] is None:
            continue
        sim[i, i] = 1.0
        for j in range(i + 1, n):
            if arrays[j] is None:
                continue
            # MinHash Jaccard estimate = count of matching hashes / num_perm
            matches = np.sum(arrays[i] == arrays[j])
            jaccard = matches / len(arrays[i])
            sim[i, j] = jaccard
            sim[j, i] = jaccard

    return sim
