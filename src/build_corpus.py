import json
import random
import statistics
from collections import Counter
from pathlib import Path

RAW = sorted(Path("data/raw").glob("*.json"))[0]
OUT = Path("data/processed")
OUT.mkdir(parents=True, exist_ok=True)

SECTIONS = [
    "boxed_warning", "indications_and_usage", "dosage_and_administration",
    "contraindications", "warnings", "warnings_and_cautions",
    "drug_interactions", "adverse_reactions",
    "use_in_specific_populations", "overdosage",
]
SAMPLE_SIZE = 2000


def clean(parts):
    return " ".join(" ".join(parts).split())


records = json.loads(RAW.read_text(encoding="utf-8"))["results"]

types = Counter()
for r in records:
    types.update(r.get("openfda", {}).get("product_type", ["(none)"]))
print("Product types:", types.most_common())

rx = [r for r in records
      if "HUMAN PRESCRIPTION DRUG" in " ".join(r.get("openfda", {}).get("product_type", []))]
print("Prescription labels:", len(rx))

print("\nSection presence among prescription labels:")
for s in SECTIONS:
    n = sum(1 for r in rx if s in r)
    print(f"{s:30s}{100 * n / len(rx):5.1f}%")

usable = [r for r in rx
          if "indications_and_usage" in r and sum(s in r for s in SECTIONS) >= 4]
print("\nUsable labels:", len(usable))

random.seed(42)
sample = random.sample(usable, min(SAMPLE_SIZE, len(usable)))

with open(OUT / "labels.jsonl", "w", encoding="utf-8") as f:
    for r in sample:
        meta = r.get("openfda", {})
        row = {
            "set_id": r["set_id"],
            "version": r["version"],
            "effective_time": r["effective_time"],
            "brand_name": (meta.get("brand_name") or [""])[0],
            "generic_name": (meta.get("generic_name") or [""])[0],
            "manufacturer": (meta.get("manufacturer_name") or [""])[0],
            "sections": {s: clean(r[s]) for s in SECTIONS if s in r},
        }
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
print("Wrote", len(sample), "labels")

print("\nSection length in characters (sample):")
for s in SECTIONS:
    lens = [len(clean(r[s])) for r in sample if s in r]
    if lens:
        print(f"{s:30s} median {int(statistics.median(lens)):6d}   max {max(lens):7d}")