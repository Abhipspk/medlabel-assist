import json
import random
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, "src")
from answer import answer_question      # noqa: E402
from retrieval import Retriever, drug_key  # noqa: E402

INTENTS = ["contraindications", "interactions", "dosage", "side_effects", "indications", "overdose"]
STOP = set("the a an of and or to in for with is are be by on at as it that this these those "
           "may should not no can has have from if than their who which was were been".split())


def words(text):
    return [w for w in re.findall(r"[a-z]+", text.lower()) if w not in STOP and len(w) > 2]


def strip_cites(text):
    return re.sub(r"\[\d+\]", " ", text)


def overlap(answer, evidence_text):
    aw = words(strip_cites(answer))
    ev = set(words(evidence_text))
    return sum(w in ev for w in aw) / len(aw) if aw else 1.0


def numbers(text):
    return set(re.findall(r"\d+(?:\.\d+)?", strip_cites(text)))


rows = [json.loads(line)
        for line in Path("eval/hard_set.jsonl").read_text(encoding="utf-8").splitlines()]
by = defaultdict(list)
for x in rows:
    by[(x["kind"], x["intent"])].append(x)

random.seed(5)
sample = []
for intent in INTENTS:
    sample += random.sample(by[("answerable", intent)], 3)
sample += random.sample(by[("out_of_scope", "none")], 12)
sample += random.sample(by[("fictional", "none")], 4)

r = Retriever()
results, md = [], ["# End-to-end answers\n"]
try:
    for i, x in enumerate(sample, 1):
        print(f"[{i}/{len(sample)}] {x['question']}", flush=True)
        out = answer_question(r, x["question"])
        ev = out["evidence"]
        cited = [ev[n - 1] for n in out["cited"]]
        pool_text = " ".join(h["text"] for h in (cited or ev))
        exp = set(x["expected"])
        res = {
            "kind": x["kind"], "intent": x["intent"], "question": x["question"],
            "abstained": out["abstained"], "reason": out["reason"],
            "uncited": out["uncited"], "seconds": out["seconds"],
            "section_ok": any(drug_key(h["generic_name"]) == x["drug"] and h["section"] in exp
                              for h in cited),
            "wrong_drug_cited": any(drug_key(h["generic_name"]) != x["drug"] for h in cited),
            "numbers_ok": numbers(out["answer"]) <= numbers(pool_text),
            "overlap": overlap(out["answer"], pool_text),
            "answer": out["answer"],
        }
        results.append(res)
        md.append(f"## {i}. [{x['kind']}/{x['intent']}] {x['question']}\n"
                  f"- abstained: {out['abstained']} ({out['reason']}), uncited: {out['uncited']}\n"
                  f"- cited sections: {[h['section'] for h in cited]}\n\n"
                  f"{out['answer']}\n")
finally:
    r.close()
    Path("eval/e2e_answers.md").write_text("\n".join(md), encoding="utf-8")
    Path("eval/results_e2e.json").write_text(json.dumps(results, indent=1), encoding="utf-8")


def rate(items, key):
    return statistics.mean(bool(v[key]) for v in items) if items else float("nan")


ans = [v for v in results if v["kind"] == "answerable"]
oos = [v for v in results if v["kind"] == "out_of_scope"]
fic = [v for v in results if v["kind"] == "fictional"]
answered = [v for v in ans if not v["abstained"]]

print(f"\nANSWERABLE (n={len(ans)})")
print(f"  answered (did not refuse):        {1 - rate(ans, 'abstained'):.2f}")
print(f"  has citation (of answered):       {1 - rate(answered, 'uncited'):.2f}")
print(f"  cited right drug+section:         {rate(answered, 'section_ok'):.2f}")
print(f"  cited wrong drug:                 {rate(answered, 'wrong_drug_cited'):.2f}")
print(f"  numbers all found in evidence:    {rate(answered, 'numbers_ok'):.2f}")
if answered:
    print(f"  mean word overlap with evidence:  {statistics.mean(v['overlap'] for v in answered):.2f}")
print(f"OUT-OF-SCOPE real drugs (n={len(oos)}): refused {rate(oos, 'abstained'):.2f}"
      f" | wrongly answered {1 - rate(oos, 'abstained'):.2f}")
print(f"INVENTED drugs (n={len(fic)}): refused {rate(fic, 'abstained'):.2f}")
llm = [v["seconds"] for v in results if v["seconds"] > 3]
if llm:
    print(f"\nmean seconds per LLM answer: {statistics.mean(llm):.0f}")

print("\nCASES TO LOOK AT")
for v in ans:
    if v["abstained"]:
        print(f"  refused good question ({v['reason']}): {v['question']}")
    elif not v["section_ok"] or not v["numbers_ok"] or v["overlap"] < 0.7:
        print(f"  weak answer (section_ok={v['section_ok']}, numbers_ok={v['numbers_ok']}, "
              f"overlap={v['overlap']:.2f}): {v['question']}")
for v in oos:
    if not v["abstained"]:
        print(f"  answered out-of-scope: {v['question']}\n      -> {v['answer'][:160]}")