import argparse
import re
import time

import requests

from retrieval import Retriever
from routing import route_sections

OLLAMA_URL = "http://localhost:11434/api/chat"
LLM = "qwen2.5:3b"
ABSTAIN_BELOW = 0.0          # placeholder; we calibrate it in the evaluation step
NO_EVIDENCE = "NOT ENOUGH EVIDENCE"

SYSTEM = (
    "You answer questions about prescription drug labels. "
    "Use ONLY the numbered excerpts provided. Do not use outside knowledge. "
    "Cite every statement with its excerpt number like [1]. "
    f"If the excerpts do not contain the answer, reply exactly: {NO_EVIDENCE}. "
    "Keep the answer under 120 words."
)


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


def answer_question(retriever, question, sections=None, route=True):
    start = time.time()
    routed = sections or (route_sections(question) if route else None)
    hits = retriever.search(question, top_k=8, sections=routed)
    if routed and (not hits or hits[0]["score"] < ABSTAIN_BELOW):
        hits = retriever.search(question, top_k=8)   # fall back to all sections
        routed = None
    top = hits[0]["score"] if hits else None

    if top is None or top < ABSTAIN_BELOW:
        return {"answer": NO_EVIDENCE, "abstained": True, "reason": "low retrieval score",
                "top_score": top, "routed": routed, "evidence": [], "cited": [],
                "uncited": False, "seconds": time.time() - start}

    evidence = dedupe(hits)
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