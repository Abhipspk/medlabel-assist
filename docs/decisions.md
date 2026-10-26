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
30. Adopted section-diverse retrieval as the route-free fallback: held-out hit@4 0.69 -> 0.79.
31. Gate 1: no recognized drug name means refuse (held-out: real drugs detected 1.00, invented 0.00). Brand-name words map to the generic key.
32. Gate 2: ABSTAIN_BELOW = 1.0, chosen safety-first from held-out calibration: keeps ~90% of answerable, blocks ~89-92% of real-drug out-of-scope. A wrong answer costs more than a refusal.
33. Known gaps: contraindications hit@4 only 0.50 on paraphrases (likely reranker domain mismatch; next experiment: a stronger reranker). ~10% of out-of-scope questions pass the score gate and must be caught by the model's refusal and the citation check, to be measured end to end.
34. End-to-end eval uses deterministic checks (citation present, cited right drug+section, numbers in answer all appear in the cited evidence, word overlap) plus a markdown file of all answers for human review. A 3B model is not a trustworthy judge of itself.
35. Refusal is tested on real-drug out-of-scope questions (price, comparison, history) and on invented drugs.
36. E2E baseline (3B, prompt v1): answered 0.78, right drug+section cited 0.71, wrong-drug 0.00, numbers faithful 1.00, out-of-scope refused 12/12, invented refused 4/4.
37. Over-refusal by the model suspected from the strict "reply exactly NOT ENOUGH EVIDENCE" instruction. Experiments change one variable each: A = partial-answer prompt (3B), B = 7B model with the original prompt.
38. One refusal came from the score gate ("poisoned" vs label word "overdosage"). Candidate fix: query expansion with medical synonyms.
39. 7B vs 3B (prompt v1): same answer rate (0.78), all answers cited, but 2x slower (33s vs 17s) and no gain in right-section citations. Same questions fail under both models, so the bottleneck is evidence or prompt, not model size. 3B kept for dev/CI/demo.
40. Checker bug: numbered-list markers were counted as "numbers not found in evidence". Fixed; evidence text now saved for re-scoring.
41. Partial-answer prompt (v2) compared with v1 on the same 34 questions under the fixed checker.
42. Prompt v2 vs v1 (3B, fixed checker, 34 questions): answered 0.78 to 0.94; out-of-scope 12/12 and invented 4/4 still refused; no wrong-drug citations. v2 made default. One numeric-faithfulness flag (ondansetron unsafe) under review. Right-section rate is not comparable across prompts because v2 answers more, harder questions.
43. Persistent section_ok=False with high word overlap (latanoprost, irbesartan, ondansetron) suggests the section check is too strict. To be verified by reading answers.
44. Out-of-scope refusals under v2 all came from the retrieval score gate, so they do not test the prompt. Prompt looseness is validated only on questions that pass the gate.
45. Manual review of 34 v2 answers: one inverted-meaning answer (ondansetron, pediatric), citation drift to label section numbers, prompt-instruction leakage (montelukast), wrong-section evidence (irbesartan side effects, ondansetron indications). Overlap metric cannot detect negation errors.
46. Decision: citation verification becomes a hard gate; an answer with no valid [n] is retried once, then replaced with a refusal. Section check kept (too strict only for latanoprost, which has no contraindications text).
47. Prompt v3 (citation-only [n], no reversal rule) plus citation gate: citations 1.00, numbers 1.00, no inverted-meaning answer; answered 0.89 (ondansetron unsafe now abstains, accepted: refusal beats an inverted answer). Overlap fell 0.74 to 0.71 and clindamycin regressed on section check; under review.
48. Query expansion applied to the search query only (LLM sees the original question) to bridge user vocabulary and label vocabulary. Success criterion: metformin poisoning answered, irbesartan side effects and ondansetron indications retrieve the right section, out-of-scope still 12/12 refused.
49. Query expansion: right-section citations 0.69 to 1.00 on the dev set, answered 0.89, out-of-scope 12/12. Caveat: rules were written while looking at these questions; generalisation is measured only on the final hand-written set. Known gaps: ertapenem interactions, montelukast poisoning still abstain.
50. Guardrails, defence in depth: gate 0 regex for direct injection (OWASP LLM01), PII redaction before search/LLM/logs, indirect-injection filter on retrieved chunks, then drug gate, score gate, prompt rules, citation gate. Regex is bypassable by paraphrase, so layers 2+ matter and are measured separately.
51. Regex PII redaction chosen over Presidio to stay light on a 16 GB laptop; Presidio is the production upgrade (NER-based, better on names).
52. Guardrail eval: regex blocked 7/10 attacks, 0/6 false positives. The 3 paraphrases that slipped were refused by the score gate, not by model resistance, so LLM-level injection resistance is not yet independently measured (future work: attacks that retrieve strongly).
53. API: FastAPI, Pydantic validation, JWT (30 min), roles analyst/auditor/admin, demo users hashed with PBKDF2 (production: SSO + secrets manager). PII redacted before search, LLM and audit log.
54. Audit log is hash-chained JSONL: edits/deletes/reorders are detectable (verify_chain). Production would use an append-only store (S3 Object Lock / WORM) with the chain as a second check.
55. LLM call runs in a worker thread behind a lock: the event loop stays responsive; concurrency is deliberately limited to 1 on a 16 GB CPU laptop.
56. Observability: per-request trace (spans retrieve/llm, queue wait, total) to logs/traces.jsonl; Prometheus metrics (/metrics): requests by decision, latency histogram. Own implementation chosen over self-hosted Langfuse: Langfuse needs Postgres+ClickHouse+Redis+object storage, too heavy for 16 GB CPU laptop beside Ollama. Span fields match Langfuse/OpenTelemetry concepts so swapping in is a small change.
57. JWT default secret lengthened (>=32 bytes) and server refuses to start in MEDLABEL_ENV=production with the default secret (fail closed).
58. Docker: slim Python 3.11 image, CPU-only torch, data/logs/model-cache mounted as volumes (image stays small, data not baked in), Ollama stays on host via host.docker.internal. /metrics is unauthenticated for local use; production would restrict it at the network layer.