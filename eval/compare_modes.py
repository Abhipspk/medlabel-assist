import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, "src")
from answer import select_evidence      # noqa: E402
from retrieval import Retriever, drug_key  # noqa: E402
from routing import route_sections      # noqa: E402

rows = [json.loads(line)
        for line in Path("eval/hard_set.jsonl").read_text(encoding="utf-8").splitlines()]
r = Retriever()
MODES = ["current", "diverse"]


def retrieve(q, mode):
    routed = route_sections(q)
    drug = r.detect_drug(q)
    if routed:
        hits = r.search_by_section(q, routed, drug=drug)
    elif mode == "diverse":
        hits = r.search_diverse(q, drug=drug)
    else:
        hits = r.search(q, top_k=8, drug=drug)
    top = max((h["score"] for h in hits), default=-99.0)
    return select_evidence(hits, routed), top


res = {m: [] for m in MODES}
for row in rows:
    exp = set(row["expected"])
    for m in MODES:
        ev, top = retrieve(row["question"], m)
        hit = any(drug_key(h["generic_name"]) == row["drug"] and h["section"] in exp for h in ev)
        res[m].append({"kind": row["kind"], "intent": row["intent"], "hit": hit, "top": top})

for m in MODES:
    ans = [x for x in res[m] if x["kind"] == "answerable"]
    print(f"\n== {m} ==  answerable hit@4 = {statistics.mean(x['hit'] for x in ans):.2f}")
    for intent in sorted({x["intent"] for x in ans}):
        sub = [x for x in ans if x["intent"] == intent]
        print(f"   {intent:18s} {statistics.mean(x['hit'] for x in sub):.2f}")

    ans_s = [x["top"] for x in ans]
    oos_s = [x["top"] for x in res[m] if x["kind"] == "out_of_scope"]
    print("   threshold  answerable_kept  real-drug_out_of_scope_blocked")
    for t in [i / 2 for i in range(-4, 9)]:
        kept = statistics.mean(s >= t for s in ans_s)
        blocked = statistics.mean(s < t for s in oos_s)
        print(f"   {t:8.1f}  {kept:15.2f}  {blocked:30.2f}")

Path("eval/results_modes.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
r.close()