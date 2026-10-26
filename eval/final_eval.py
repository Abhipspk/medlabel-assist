import json
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, "src")
from answer import answer_question          # noqa: E402
from gate import failures, metrics          # noqa: E402
from retrieval import Retriever, drug_key   # noqa: E402

STOP = set("the a an of and or to in for with is are be by on at as it that this these those "
           "may should not no can has have from if than their who which was were been".split())


def words(t):
    return [w for w in re.findall(r"[a-z]+", t.lower()) if w not in STOP and len(w) > 2]


def strip_cites(t):
    return re.sub(r"\[\d+\]", " ", t)


def numbers(t):
    t = re.sub(r"(?m)^\s*\d+[.)]\s+", " ", strip_cites(t))
    return set(re.findall(r"\d+(?:\.\d+)?", t))


def overlap(a, ev):
    aw, ew = words(strip_cites(a)), set(words(ev))
    return sum(w in ew for w in aw) / len(aw) if aw else 1.0


rows = [json.loads(line) for line in
        Path("eval/final_set.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
for x in rows:
    assert x["kind"] in ("answerable", "out_of_scope", "injection", "fictional"), x
    if x["kind"] == "answerable":
        assert x.get("drug") and x.get("expected"), f"answerable needs drug + expected: {x}"

r = Retriever()
results, md = [], ["# Final held-out answers\n"]
try:
    for i, x in enumerate(rows, 1):
        print(f"[{i}/{len(rows)}] {x['question']}", flush=True)
        out = answer_question(r, x["question"])
        refused = out["abstained"]
        if x["kind"] == "injection" and x.get("canary"):
            refused = x["canary"].lower() not in out["answer"].lower()   # obeying = leak
        ev = out["evidence"]
        cited = [ev[n - 1] for n in out["cited"]]
        pool = " ".join(h["text"] for h in (cited or ev))
        drug, exp = x.get("drug"), set(x.get("expected", []))
        results.append({
            "kind": "out_of_scope" if x["kind"] == "injection" else x["kind"],
            "orig_kind": x["kind"], "question": x["question"],
            "abstained": refused, "reason": out["reason"], "uncited": out["uncited"],
            "section_ok": any(drug_key(h["generic_name"]) == drug and h["section"] in exp for h in cited),
            "wrong_drug_cited": any(drug_key(h["generic_name"]) != drug for h in cited) if drug else False,
            "numbers_ok": numbers(out["answer"]) <= numbers(pool),
            "overlap": overlap(out["answer"], pool), "answer": out["answer"],
        })
        md.append(f"## {i}. [{x['kind']}] {x['question']}\n- {out['reason']}; "
                  f"cited sections: {[h['section'] for h in cited]}\n\n{out['answer']}\n")
finally:
    r.close()
    Path("eval/final_answers.md").write_text("\n".join(md), encoding="utf-8")
    Path("eval/results_final.json").write_text(json.dumps(results, indent=1), encoding="utf-8")

m = metrics(results)
print("\nFINAL HELD-OUT RESULT")
for k, v in m.items():
    print(f"  {k:34s} {v:.2f}")
bad = failures(m)
print("\nPASSES the project's quality bar" if not bad else "\nBELOW the bar: " + "; ".join(bad))
print("\nPER QUESTION")
for v in results:
    flag = ("ok" if v["abstained"] else "LEAKED") if v["kind"] != "answerable" else \
           ("REFUSED" if v["abstained"] else ("ok" if v["section_ok"] and v["numbers_ok"] else "WEAK"))
    print(f"  {flag:8s} {v['orig_kind']:13s} ({v['reason']}) {v['question'][:70]}")