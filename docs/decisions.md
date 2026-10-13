1. Source: openFDA bulk labels, first partition only. CC0, no API key or cost.
2. Filter: prescription labels only. 16,016 records lacked product_type and were excluded (known limitation).
3. Chunking: ~1000 chars, sentence boundaries, 1-sentence overlap, contextual header per chunk.
4. Missing section: system states the section is absent; it never guesses.
5. Embedding model: bge-small-en-v1.5 (free, CPU-friendly). Measured 45s per 500 chunks, so full corpus would take ~105 min.
6. Development corpus: 300 labels (~12k chunks), checkpointed in 2000-chunk shards. Full corpus is reserved for a final overnight run.
7. If chunking or N_LABELS changes, delete data/embeddings/ so vectors match chunks.
8. Vector store changed from pgvector to Qdrant (local mode): pgvector on Windows needs Docker, which comes later. Qdrant also supports payload filters for access control.
9. Hybrid retrieval: dense + BM25 merged with reciprocal rank fusion (RRF).