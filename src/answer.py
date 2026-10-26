import argparse
import re
import time
import os

import requests

from retrieval import Retriever
from routing import route_sections

OLLAMA_URL = "http://localhost:11434/api/chat"
LLM = os.environ.get("MEDLABEL_LLM", "qwen2.5:3b")
ABSTAIN_BELOW = 1.0          # calibrated on the held-out set (see docs/decisions.md)
NO_EVIDENCE = "NOT ENOUGH EVIDENCE"
NO_DRUG = ("I could not identify a drug from the labels in this dataset. "
           "Please name the drug your question is about.")

SYSTEM_V1 = (
    "You answer questions about prescription drug labels. "
    "Use ONLY the numbered excerpts provided. Do not use outside knowledge. "
    "Cite every statement with its excerpt number like [1]. "
    "Preserve qualifiers exactly: words like 'unless', 'only if', 'initiate', numbers and thresholds. "
    "If several excerpts are relevant, cover each distinct point separately. "
    f"If the excerpts do not contain the answer, reply exactly: {NO_EVIDENCE}. "
    "Keep the answer under 150 words."
)

SYSTEM_V2 = (
    "You answer questions about prescription drug labels. "
    "Use ONLY the numbered excerpts provided. Do not use outside knowledge. "
    "Cite every statement with its excerpt number like [1]. "
    "Preserve qualifiers exactly: words like 'unless', 'only if', 'initiate', numbers and thresholds. "
    "If several excerpts are relevant, cover each distinct point separately. "
    "If the excerpts answer only part of the question, give the part they support "
    "and say what is not covered. "
    f"Reply exactly {NO_EVIDENCE} only when none of the excerpts is relevant to the question. "
    "Keep the answer under 150 words."
)
SYSTEM = SYSTEM_V1 if os.environ.get("MEDLABEL_PROMPT") == "v1" else SYSTEM_V2


def dedupe(hits, limit=4):
    """Same drug + same section + same position in the section = same content
    from different manufacturers. Keep the best-scoring one and count the rest."""
    best = {}
    for h in hits:
        position = h["chunk_id"].rsplit(":", 1)[-1]
        key = (h["generic_name"].lower(), h["section"], position)
        if key in best:
            best[key]["n_labels"] += 1
        else:
            best[key] = {**h, "n_labels": 1}
    return list(best.values())[:limit]


def select_evidence(hits, routed, limit=4):
    """Guarantee the best chunk from each routed section (in priority order),
    then fill remaining slots by score."""
    unique = dedupe(hits, limit=len(hits))
    chosen = []

    def taken():
        return {c["chunk_id"] for c in chosen}

    for sec in routed or []:
        for h in unique:
            if h["section"] == sec and h["chunk_id"] not in taken():
                chosen.append(h)
                break
    for h in unique:
        if len(chosen) >= limit:
            break
        if h["chunk_id"] not in taken():
            chosen.append(h)
    return chosen[:limit]


def build_context(evidence):
    blocks = []
    for n, h in enumerate(evidence, 1):
        blocks.append(f"[{n}] {h['generic_name']} | {h['section']} | {h['manufacturer']}\n{h['text']}")
    return "\n\n".join(blocks)


def call_llm(question, context):
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": LLM,
                "stream": False,
                "options": {"temperature": 0, "num_ctx": 4096},
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": f"Excerpts:\n{context}\n\nQuestion: {question}"},
                ],
            },
            timeout=600,
        )
    except requests.exceptions.ConnectionError:
        raise SystemExit("Cannot reach Ollama at localhost:11434. "
                         "Start the Ollama app (or run 'ollama serve') and try again.")
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def gather(retriever, question, drug, sections=None, route=True):
    """The single retrieval path used by the app and the evaluations."""
    routed = sections or (route_sections(question) if route else None)
    if routed:
        hits = retriever.search_by_section(question, routed, drug=drug)
    else:
        hits = retriever.search_diverse(question, drug=drug)
    top = max((h["score"] for h in hits), default=None)
    if routed and (top is None or top < ABSTAIN_BELOW):
        hits = retriever.search_diverse(question, drug=drug)   # router missed: go route-free
        routed = None
        top = max((h["score"] for h in hits), default=None)
    return hits, routed, top


def _refusal(answer, reason, top, routed, start):
    return {"answer": answer, "abstained": True, "reason": reason, "top_score": top,
            "routed": routed, "evidence": [], "cited": [], "uncited": False,
            "seconds": time.time() - start}


def answer_question(retriever, question, sections=None, route=True):
    start = time.time()
    drug = retriever.detect_drug(question)
    if drug is None:                                   # gate 1: no recognized drug
        return _refusal(NO_DRUG, "no recognized drug", None, None, start)

    hits, routed, top = gather(retriever, question, drug, sections, route)
    if top is None or top < ABSTAIN_BELOW:             # gate 2: weak evidence
        return _refusal(NO_EVIDENCE, "low retrieval score", top, routed, start)

    evidence = select_evidence(hits, routed)
    text = call_llm(question, build_context(evidence))
    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", text)
                    if 1 <= int(n) <= len(evidence)})
    abstained = NO_EVIDENCE in text
    return {"answer": text, "abstained": abstained,
            "reason": "model abstained" if abstained else "answered",
            "top_score": top, "routed": routed, "evidence": evidence, "cited": cited,
            "uncited": (not abstained and not cited),
            "seconds": time.time() - start}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--sections", default=None, help="comma-separated section names")
    ap.add_argument("--no-route", action="store_true")
    ap.add_argument("--show-evidence", action="store_true")
    args = ap.parse_args()
    secs = args.sections.split(",") if args.sections else None

    r = Retriever()
    try:
        out = answer_question(r, args.question, secs, route=not args.no_route)
    finally:
        r.close()

    print("\nANSWER:", out["answer"])
    print(f"\nrouted={out['routed']} | abstained={out['abstained']} ({out['reason']}) "
          f"| top_score={out['top_score']} | uncited={out['uncited']} | {out['seconds']:.0f}s")
    for n in out["cited"]:
        h = out["evidence"][n - 1]
        print(f"  [{n}] {h['generic_name'][:30]} | {h['section']} | {h['manufacturer'][:25]} "
              f"| seen in {h['n_labels']} label(s)")
    if args.show_evidence:
        print("\n--- EVERYTHING THE MODEL SAW ---")
        for n, h in enumerate(out["evidence"], 1):
            print(f"\n[{n}] {h['section']} | score={h['score']:.2f}\n{h['text'][:500]}")