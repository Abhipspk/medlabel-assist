# MedLabel Assist

A regulated-industry knowledge copilot: ask questions about FDA prescription drug labels and get **cited answers, or a refusal**. Built only with free, local, open-source tools (no paid APIs).

> **Not medical advice.** Answers come from FDA label text only. Always verify against the full official label.
> Data provided by the U.S. Food and Drug Administration (https://open.fda.gov). openFDA data is CC0.

## Why this project

In pharma, a confident wrong answer is worse than no answer. So the system is built around three rules: answer only from retrieved label text, cite every statement, and refuse when evidence is weak. Every safety claim below is backed by an evaluation in `eval/`, and every design choice is logged in `docs/decisions.md` (60+ entries).

## Architecture

~~~mermaid
flowchart LR
  U[User with JWT] --> API[FastAPI ask endpoint]
  API --> PII[PII redaction]
  PII --> G0{Injection filter}
  G0 -->|blocked| R[Refuse]
  G0 --> D{Drug recognised}
  D -->|no| R
  D --> X[Query expansion]
  X --> RT[Routing or section-diverse retrieval]
  RT --> H[Hybrid search: dense plus BM25 plus RRF]
  H --> RR[Cross-encoder rerank]
  RR --> S{Score at least 1.0}
  S -->|no| R
  S --> E[Evidence selection plus injection scan]
  E --> L[Qwen 2.5 3B via Ollama]
  L --> C{Valid citation}
  C -->|no, retry once| L
  C -->|still no| R
  C --> A[Answer with citations and disclaimer]
  A --> AU[(Hash-chained audit log)]
  R --> AU
~~~

## Safety layers (defence in depth)

1. PII redaction before search, LLM and logs
2. Prompt-injection filter on questions and on retrieved chunks (OWASP LLM01)
3. Drug gate: no recognised drug, no answer
4. Score gate (threshold 1.0, calibrated on held-out data)
5. Prompt rules: cite only excerpt numbers, never reverse meaning, refuse if irrelevant
6. Citation gate: an answer without a valid citation is retried once, then refused
7. Role-based access (analyst, auditor, admin) with JWT, and a tamper-evident audit log

## Results (honest version)

| Test | Result |
|---|---|
| Retrieval ablation, templated golden set (72 q) | hit@4: hybrid 0.86 -> +rerank 0.90 -> +routing 0.97 -> +drug filter 0.96 -> +per-section 1.00 (saturated, regression only) |
| Paraphrased questions (72 q, router bypassed) | hit@4 0.69 -> 0.85 with section-diverse retrieval |
| Dev end-to-end (34 q, tuned on) | answered 0.83, right section 1.00, numbers 1.00, 12/12 out-of-scope and 4/4 invented refused |
| Out-of-scope sweep (46 q) | 0 answered; refused by score gate 31, drug gate 10, model 5 |
| **Fresh held-out set (24 q, not used for tuning)** | answered 10/12; of those, right section, numbers and citations 10/10; 0/6 out-of-scope answered; 0/3 injections leaked; 3/3 invented refused |
| 3B vs 7B model | same answer rate, 7B 2x slower with no quality gain, so 3B kept |
| Scale: 300 -> 1,704 labels (67,002 chunks) | metrics held or improved; threshold 1.0 still best |

## Quick start

~~~
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
ollama pull qwen2.5:3b
python src/download_labels.py
python src/build_corpus.py
python src/build_chunks.py
python src/embed_chunks.py     # slow on CPU, checkpointed and resumable
python src/index_qdrant.py
uvicorn api:app --app-dir src  # then open http://127.0.0.1:8000/docs
~~~

Docker: `docker compose up --build` (Ollama stays on the host). Tests: `python -m pytest -q`. Evaluation: `python eval/e2e_eval.py` then `python eval/check_gate.py`.

## Layout

- `src/` pipeline (chunking, retrieval, routing, expansion, answer, guardrails, verify), API (api, auth, audit, tracing), AWS demo (aws_archive), CI gate (gate)
- `eval/` retrieval, hard, end-to-end, out-of-scope, guardrail and final held-out evaluations, with saved results
- `tests/` unit and API tests (test doubles, no models needed)
- `docs/decisions.md` every decision and its evidence; `docs/aws_mapping.md` laptop-to-AWS design; `docs/INTERVIEW.md` defence sheet
- `infra/iam_policy.json` least-privilege policy tested with moto; `.github/workflows/ci.yml` tests plus evaluation gate

## Known limitations

- First openFDA partition only: 1,704 usable prescription labels; 16,016 records excluded for missing product type.
- Evaluation sets are small (the held-out set has 12 answerable questions, so confidence intervals are wide); the dev sets are templated and were used for tuning.
- Drug detection keys on the first word of the generic name; combination products and names starting with "sodium" are weak.
- Query expansion is rule-based and brittle on unseen phrasing (held-out miss: "must never be given").
- A 3B CPU model takes 16-25 s per answer and refuses about 17% of answerable questions.
- LLM-level injection resistance is not measured independently; the test attacks were stopped by earlier gates.
- No policy for personal medical advice: a personally phrased question ("how many tablets should I take tonight") is answered with the label's general dosing text instead of being declined.
- Qdrant runs in local mode (server mode recommended above 20k points); the reranker was trained on web search, not clinical text.
- CI gates the committed evaluation results; the LLM evaluation itself runs locally.
- AWS pieces are mocked with moto, not run against a real account.
