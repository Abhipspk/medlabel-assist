import json
from pathlib import Path
from collections import Counter

files = sorted(Path("data/raw").glob("*.json"))
print("JSON files:", [f.name for f in files])
data = json.loads(files[0].read_text(encoding="utf-8"))
print("Top-level keys:", list(data.keys()))
records = data["results"]
print("Records in this file:", len(records))

counts = Counter()
for rec in records:
    counts.update(rec.keys())
print("\nField presence (% of records):")
for field, c in counts.most_common(25):
    print(f"{field:35s} {100 * c / len(records):5.1f}%")

rec = records[0]
meta = rec.get("openfda", {})
print("\nSample drug:", {k: meta.get(k, ["?"])[:1] for k in ("brand_name", "generic_name", "manufacturer_name")})
for field in ("indications_and_usage", "contraindications", "drug_interactions"):
    text = " ".join(rec.get(field, ["(missing)"]))
    print(f"\n{field} ({len(text)} chars):\n{text[:300]}")