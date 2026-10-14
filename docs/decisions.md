1. Source: openFDA bulk labels, first partition only. CC0, no API key or cost.
2. Filter: prescription labels only. 16,016 records lacked product_type and were excluded (known limitation).
3. Chunking: ~1000 chars, sentence boundaries, 1-sentence overlap, contextual header per chunk.
4. Missing section: system states the section is absent; it never guesses.
5. Embedding model: bge-small-en-v1.5 (free, CPU-friendly). Measured 45s per 500 chunks, so full corpus would take ~105 min.
6. Development corpus: 300 labels (~12k chunks), checkpointed in 2000-chunk shards. Full corpus is reserved for a final overnight run.
7. If chunking or N_LABELS changes, delete data/embeddings/ so vectors match chunks.
8. Vector store changed from pgvector to Qdrant (local mode): pgvector on Windows needs Docker, which comes later. Qdrant also supports payload filters for access control.
9. Hybrid retrieval: dense + BM25 merged with reciprocal rank fusion (RRF).
10. Reranker: cross-encoder MiniLM-L-6 on top-20 fused candidates (fast on CPU). bge-reranker-base is the quality upgrade if latency allows.
11. Section filter applied in both dense (Qdrant filter) and BM25 (score mask) so routing is consistent.
12. Dedupe: same drug + section + position across manufacturers collapses to one evidence item, with a count of agreeing labels.
13. Abstention: (a) retrieval-score gate, (b) model instructed to reply NOT ENOUGH EVIDENCE, (c) post-check flags answers with no valid citation.
14. LLM settings: temperature 0, num_ctx 4096, max 4 excerpts of ~1000 chars.
15. Failure found: "Who should not take X?" retrieved dosage text (cited but off-topic). Cause: question never says "contraindication".
16. Fix: rule-based router maps question intent to section filters, with fallback to all sections if routed search finds nothing good. Chosen for transparency, auditability and zero latency; its limit is paraphrases it has no rule for, which the evaluation set will measure.
17. Routing alone was not enough: the 3B model cited one warnings excerpt and dropped a qualifier. Added coverage-aware evidence selection (one slot per routed section), a prompt that preserves qualifiers, and --show-evidence for debugging.
18. Anecdotal debugging replaced by a retrieval eval: 72 templated questions (12 drugs x 6 intents), strict pass = right drug AND right section in the 4 evidence chunks.
19. Drug-name filter added (drug key = first meaningful word of generic name). Prevents cross-drug contamination, a safety risk.
20. Known weakness of this eval: templated questions are easy and match our router's rules, so scores are optimistic. Hand-written paraphrases and unanswerable questions come next.
21. Eval findings: routing gave the largest gain (MRR 0.78 -> 0.96) but let other drugs leak in (drug precision 0.69); the drug filter fixed that (1.00).
22. The MS MARCO reranker hurt the contraindications intent (0.83 -> 0.50): domain mismatch. Candidate fixes: per-section retrieval (config E), a stronger reranker, or a domain-tuned one.
23. Caveat: 12 questions per intent and templated wording, so scores are optimistic and differences of one question are noise.
24. Config E scored 1.00 on templated questions, but those match router keywords and were used for tuning, so they are not a fair test.
25. Held-out hard set: 12 different drugs, paraphrased questions that avoid router keywords, out-of-scope questions about real drugs, and invented drug names.
26. ABSTAIN_BELOW to be set from measured score separation, not guessed.
27. Held-out paraphrases scored hit@4 0.69 (vs 1.00 on templates): the rule router never fired. Rules memorize wording; the data says do not extend them.
28. Candidate fix: section-diverse retrieval (best chunk per section, then top 4 by score), measured against the plain fallback on the same held-out set.
29. Drug gate proposed: no recognized drug name means refuse. Held-out data: real drugs detected 1.00, invented 0.00.