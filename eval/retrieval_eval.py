import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "src")
from answer import select_evidence      # noqa: E402
from retrieval import Retriever, drug_key  # noqa: E402
from routing import route_sections      # noqa: E402

INTENTS = [
    ("contraindications", "Who should not take {d}?", {"contraindications"}),
    ("interactions", "What other drugs interact with {d}?", {"drug_interactions"}),
    ("dosage", "What is the recommended dose of {d}?", {"dosage_and_administration"}),
    ("side_effects", "What are the common side effects of {d}?", {"adverse_reactions"}),
    ("indications", "What is {d} used to treat?", {"indications_and_usage"}),
    ("overdose", "What happens if someone takes too much {d}?", {"overdosage"}),
]

CONFIGS = [
    ("A hybrid only",              dict(rerank=False, route=False, drug=False)),
    ("B + rerank",                 dict(rerank=True, route=False, drug=False)),
    ("C + rerank + routing",       dict(rerank=True, route=True, drug=False)),
    ("D + routing + drug filter",  dict(rerank=True, route=True, drug=True)),
    ("E + per-section search",     dict(rerank=True, route=True, drug=True, per_section=True)),
]

N_DRUGS = 12
GOLDEN = Path("eval/golden_retrieval.jsonl")

r = Retriever()


def build_golden():
    sections = defaultdict(set)
    for c in r.chunks:
        sections[drug_key(c["generic_name"])].add(c["section"])
    needed = set().union(*[i[2] for i in INTENTS])
    ok = sorted(k for k, s in sections.items() if k and needed <= s)
    random.seed(11)
    picked = random.sample(ok, min(N_DRUGS, len(ok)))
    rows = [{"drug": k, "intent": n, "question": t.format(d=k), "expected": sorted(e)}
            for k in picked for n, t, e in INTENTS]
    GOLDEN.parent.mkdir(exist_ok=True)
    with GOLDEN.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return rows


def load_golden():
    if GOLDEN.exists():
        with GOLDEN.open(encoding="utf-8") as f:
            return [json.loads(line) for line in f]
    return build_golden()


def run(row, cfg):
    q = row["question"]
    routed = route_sections(q) if cfg["route"] else None
    drug = r.detect_drug(q) if cfg["drug"] else None
    if routed and cfg.get("per_section"):
        hits = r.search_by_section(q, routed, drug=drug, rerank=cfg["rerank"])
    else:
        hits = r.search(q, top_k=8, sections=routed, drug=drug, rerank=cfg["rerank"])
    if routed and not hits:
        hits = r.search(q, top_k=8, drug=drug, rerank=cfg["rerank"])
    ev = select_evidence(hits, routed)
    rel = [drug_key(h["generic_name"]) == row["drug"] and h["section"] in row["expected"]
           for h in ev]
    right_drug = [drug_key(h["generic_name"]) == row["drug"] for h in ev]
    return {
        "hit": any(rel),
        "rr": next((1 / (i + 1) for i, x in enumerate(rel) if x), 0.0),
        "drug_prec": sum(right_drug) / len(ev) if ev else 0.0,
        "sections": [h["section"] for h in ev],
    }

rows = load_golden()
print(f"{len(rows)} questions over {len({x['drug'] for x in rows})} drugs\n")

results = {}
for name, cfg in CONFIGS:
    results[name] = [run(row, cfg) for row in rows]

print(f"{'config':28s} {'hit@4':>7s} {'MRR':>7s} {'drugPrec':>9s}")
for name, res in results.items():
    n = len(res)
    print(f"{name:28s} {sum(x['hit'] for x in res) / n:7.2f} "
          f"{sum(x['rr'] for x in res) / n:7.2f} {sum(x['drug_prec'] for x in res) / n:9.2f}")

print("\nhit@4 by intent")
print(f"{'intent':20s}" + "".join(f"{n[:1]:>6s}" for n, _ in CONFIGS))
for intent, _, _ in INTENTS:
    idx = [i for i, row in enumerate(rows) if row["intent"] == intent]
    line = "".join(f"{sum(results[n][i]['hit'] for i in idx) / len(idx):6.2f}" for n, _ in CONFIGS)
    print(f"{intent:20s}{line}")

for name, _ in CONFIGS[-2:]:
    print(f"\nFailures under '{name}':")
    for row, res in zip(rows, results[name]):
        if not res["hit"]:
            print(f"  {row['question']} | expected {row['expected']} | got {res['sections']}")

Path("eval/results_retrieval.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
r.close()