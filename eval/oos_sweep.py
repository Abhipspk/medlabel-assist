import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, "src")
from answer import answer_question  # noqa: E402
from retrieval import Retriever     # noqa: E402

rows = [json.loads(line)
        for line in Path("eval/hard_set.jsonl").read_text(encoding="utf-8").splitlines()]
todo = [x for x in rows if x["kind"] in ("out_of_scope", "fictional")]

r = Retriever()
reasons, leaked = Counter(), []
try:
    for i, x in enumerate(todo, 1):
        out = answer_question(r, x["question"])
        reasons[out["reason"]] += 1
        print(f"[{i}/{len(todo)}] {out['reason']:24s} {x['question']}", flush=True)
        if not out["abstained"]:
            leaked.append((x["question"], out["answer"]))
finally:
    r.close()

print("\nWHO REFUSED (by layer):")
for reason, n in reasons.most_common():
    print(f"  {n:3d}  {reason}")
print(f"\nANSWERED A QUESTION WE SHOULD REFUSE: {len(leaked)}/{len(todo)}")
for q, a in leaked:
    print(f"  Q: {q}\n  A: {a[:300]}\n")