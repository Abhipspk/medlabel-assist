import json
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "src")
from answer import select_evidence      # noqa: E402
from retrieval import Retriever, drug_key  # noqa: E402
from routing import route_sections      # noqa: E402

PARAPHRASES = [
    ("contraindications", "In which patients is {d} unsafe?", {"contraindications"}),
    ("interactions", "Can {d} be used safely alongside other medicines?", {"drug_interactions"}),
    ("dosage", "How is the daily amount of {d} usually decided?", {"dosage_and_administration"}),
    ("side_effects", "What unwanted effects might {d} cause?", {"adverse_reactions"}),
    ("indications", "Why would a doctor give a patient {d}?", {"indications_and_usage"}),
    ("overdose", "What should be done if someone is poisoned by {d}?", {"overdosage"}),
]
OUT_OF_SCOPE = [
    "What is the price of {d} at pharmacies in Hyderabad?",
    "Is {d} better than ibuprofen?",
    "Which company first invented {d}?",
]
FICTIONAL = ["zorvexin", "plantrilex", "quenomab", "dravelitol", "mirotazine"]
FICTIONAL_TEMPLATES = ["What is {d} used for?", "Who should not take {d}?"]
HARD = Path("eval/hard_set.jsonl")

r = Retriever()


def build():
    used = {json.loads(line)["drug"]
            for line in Path("eval/golden_retrieval.jsonl").read_text(encoding="utf-8").splitlines()}
    sections = defaultdict(set)
    for c in r.chunks:
        sections[drug_key(c["generic_name"])].add(c["section"])
    needed = set().union(*[p[2] for p in PARAPHRASES])
    ok = sorted(k for k, s in sections.items() if k and k not in used and needed <= s)
    random.seed(23)
    picked = random.sample(ok, min(12, len(ok)))
    rows = []
    for k in picked:
        for intent, tpl, exp in PARAPHRASES:
            rows.append({"kind": "answerable", "drug": k, "intent": intent,
                         "question": tpl.format(d=k), "expected": sorted(exp)})
        for tpl in OUT_OF_SCOPE:
            rows.append({"kind": "out_of_scope", "drug": k, "intent": "none",
                         "question": tpl.format(d=k), "expected": []})
    for d in FICTIONAL:
        for tpl in FICTIONAL_TEMPLATES:
            rows.append({"kind": "fictional", "drug": d, "intent": "none",
                         "question": tpl.format(d=d), "expected": []})
    HARD.write_text("\n".join(json.dumps(x) for x in rows) + "\n", encoding="utf-8")
    return rows


def load():
    if HARD.exists():
        return [json.loads(line) for line in HARD.read_text(encoding="utf-8").splitlines()]
    return build()


def run(row):
    q = row["question"]
    routed = route_sections(q)
    drug = r.detect_drug(q)
    if routed:
        hits = r.search_by_section(q, routed, drug=drug)
    else:
        hits = r.search(q, top_k=8, drug=drug)
    top = max((h["score"] for h in hits), default=-99.0)
    ev = select_evidence(hits, routed)
    exp = set(row["expected"])
    hit = any(drug_key(h["generic_name"]) == row["drug"] and h["section"] in exp for h in ev)
    return {"kind": row["kind"], "intent": row["intent"], "routed": bool(routed),
            "drug_found": drug is not None, "top": top, "hit": hit}


rows = load()
results = [run(x) for x in rows]
Path("eval/results_hard.json").write_text(json.dumps(results, indent=1), encoding="utf-8")

kinds = defaultdict(list)
for x in results:
    kinds[x["kind"]].append(x)
print({k: len(v) for k, v in kinds.items()}, "\n")

ans = kinds["answerable"]
print(f"ANSWERABLE paraphrases: hit@4 = {statistics.mean(x['hit'] for x in ans):.2f}")
print(f"  router matched a rule: {statistics.mean(x['routed'] for x in ans):.2f} of questions")
for flag in (True, False):
    sub = [x for x in ans if x["routed"] == flag]
    if sub:
        print(f"  hit@4 when routed={flag}: {statistics.mean(x['hit'] for x in sub):.2f} (n={len(sub)})")
print("  hit@4 by intent:")
for intent in sorted({x["intent"] for x in ans}):
    sub = [x for x in ans if x["intent"] == intent]
    print(f"    {intent:18s} {statistics.mean(x['hit'] for x in sub):.2f}")

print("\nDRUG NAME DETECTED (should be ~1.0 for real drugs, 0.0 for invented):")
for k, v in kinds.items():
    print(f"  {k:13s} {statistics.mean(x['drug_found'] for x in v):.2f}")

print("\nTOP RERANK SCORE by kind (min / median / max):")
for k, v in kinds.items():
    s = [x["top"] for x in v]
    print(f"  {k:13s} {min(s):6.2f} {statistics.median(s):6.2f} {max(s):6.2f}")

ans_s = [x["top"] for x in ans]
bad_s = [x["top"] for k, v in kinds.items() if k != "answerable" for x in v]
print("\nthreshold  answerable_kept  unanswerable_blocked")
best = (-1, 0.0)
for t in [i / 2 for i in range(-12, 13)]:
    kept = statistics.mean(s >= t for s in ans_s)
    blocked = statistics.mean(s < t for s in bad_s)
    print(f"{t:8.1f}  {kept:15.2f}  {blocked:20.2f}")
    if (kept + blocked) / 2 > best[0]:
        best = ((kept + blocked) / 2, t)
print(f"\nBest balanced threshold: {best[1]} (balanced accuracy {best[0]:.2f})")
r.close()