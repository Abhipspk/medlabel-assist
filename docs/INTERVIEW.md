# Defend this project: interview sheet

## 30-second pitch

I built a RAG copilot over FDA drug labels for a regulated setting. It answers only from retrieved text, cites every claim, and refuses when evidence is weak. I measured it at three levels (retrieval, end to end, and a fresh held-out set), added guardrails, role-based access, a tamper-evident audit log, Docker and CI with a safety gate. Everything runs locally on a 16 GB laptop with open-source tools.

## Questions I should expect

**Why RAG and not fine-tuning?**
Labels change (versions, effective dates), and in pharma every claim must trace to a source. RAG gives citations and updates by re-indexing; fine-tuning bakes in facts I cannot cite.

**Why hybrid retrieval?**
Dense vectors catch meaning; BM25 catches exact drug names and doses. I fuse the two ranked lists with reciprocal rank fusion (k=60) because it needs no score calibration. In my ablation, hybrid alone gave hit@4 0.86; reranking, routing and per-section search then took the templated set to 1.00.

**Why a cross-encoder reranker, and what went wrong with it?**
Scoring each candidate jointly with the query is more accurate than comparing vectors. But my model was trained on web search, so it hurt contraindication queries until I added section routing and per-section search. Next experiment: a stronger or clinical reranker.

**How do you know it does not hallucinate?**
I do not claim it never does. I check: every answer needs a valid citation (retry once, else refuse), every number must appear in the cited text, and out-of-scope questions are refused by layered gates. Measured: 0 of 55 should-refuse questions answered. Limit: numeric and overlap checks cannot catch a reversed meaning; I found one such answer by reading outputs, which is why prompt v3 forbids reversals and why I review samples by hand.

**What was your worst failure and how did you find it?**
An answer saying ondansetron is unsafe in children 4 and older when the label says safety is established. Automated metrics rated it fine (word overlap 0.84). I found it by human review, then added a no-reversal rule and a hard citation gate.

**How did you choose the refusal threshold?**
Calibrated on a held-out set: answerable kept vs unanswerable blocked at each cutoff. 1.0 gave the best balance (about 0.94 kept, 0.86 to 0.92 blocked). In a regulated setting a wrong answer costs more than a refusal, so I lean strict, and the model plus the citation gate catch what slips through (5 of 5 in the sweep).

**Why a 3B model?**
CPU-only 16 GB laptop and zero budget. I tested 7B: same answer rate, twice as slow, no quality gain, so the bottleneck was evidence and prompt, not model size.

**How do you evaluate honestly?**
Three tiers: a templated golden set (saturated, regression only), a paraphrase set (the one that discriminates), and a fresh held-out set run once. I report the small n and wide confidence intervals, and I list where dev numbers are optimistic.

**Prompt injection and PII?**
Regex filter on questions and on retrieved chunks (indirect injection), PII redaction before search, LLM and logs, plus the drug and score gates and prompt rules. Honest gap: the regex is bypassable by paraphrase, and LLM-level resistance is not measured independently because later gates stopped my attacks first.

**Access control and audit?**
JWT login with roles (analyst asks, auditor reads logs, admin both). The audit log is hash-chained JSONL: editing or deleting any line breaks verification. In production: S3 Object Lock (WORM), demonstrated with moto, plus a least-privilege IAM policy asserted by a test.

**What changed when you scaled from 300 to 1,704 labels?**
I expected the score gate to degrade. It did not: paraphrase hit@4 rose from 0.79 to 0.85 and threshold 1.0 stayed best. Qdrant local mode warns above 20k points, so production would use server mode.

**What bug taught you the most?**
A stale-results bug: my evaluation tagged output files with a default prompt name that no longer matched the code, so the CI gate read old results. Lesson: gates must read what the last run actually produced; fixed with a canonical latest-results file.

**What does it NOT do well?**
It refuses about 17% of answerable questions. Query expansion is rule-based and missed "must never be given". It does not decline personal medical advice (it answers "how many tablets should I take tonight" with general label dosing). I know these gaps and have a plan for each.

**How would this run on AWS?**
See `docs/aws_mapping.md`: Bedrock for the LLM and embeddings, OpenSearch hybrid or Aurora pgvector for retrieval, ECS Fargate for the API, Cognito for identity, S3 Object Lock for audit, CloudWatch and X-Ray for traces, Secrets Manager for keys.

**What would you do next?**
Replace rule-based query expansion with a learned or LLM-based rewriter, evaluate a stronger reranker, add a personal-advice policy, run injection attacks that actually reach the model, enlarge the held-out set with real users' questions, and move to a Qdrant server.

## Numbers to remember

- Paraphrase hit@4: 0.69 -> 0.85
- Held-out: 10 of 12 answered, 10 of 10 cited correctly, 0 of 55 should-refuse questions answered
- 3B model: 16 to 25 seconds per answer
- 67,002 chunks, 1,704 labels, 60+ logged decisions
