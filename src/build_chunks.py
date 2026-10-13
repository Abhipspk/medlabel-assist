import json
import statistics
from collections import Counter
from pathlib import Path

from chunking import chunk_text

ALIASES = {"warnings_and_cautions": "warnings"}
SRC = Path("data/processed/labels.jsonl")
OUT = Path("data/processed/chunks.jsonl")

rows = [json.loads(line) for line in SRC.open(encoding="utf-8")]
chunks = []
for row in rows:
    merged = {}
    for sec, text in row["sections"].items():
        name = ALIASES.get(sec, sec)
        merged[name] = f"{merged[name]} {text}" if name in merged else text
    for sec, text in merged.items():
        header = f"Drug: {row['brand_name']} ({row['generic_name']}) | Section: {sec}"
        for i, piece in enumerate(chunk_text(text)):
            chunks.append({
                "chunk_id": f"{row['set_id']}:{sec}:{i}",
                "set_id": row["set_id"],
                "brand_name": row["brand_name"],
                "generic_name": row["generic_name"],
                "manufacturer": row["manufacturer"],
                "section": sec,
                "text": piece,
                "embed_text": f"{header}\n{piece}",
            })

with OUT.open("w", encoding="utf-8") as f:
    for c in chunks:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")

lens = [len(c["text"]) for c in chunks]
print("Labels:", len(rows), "| Chunks:", len(chunks))
print("Chunk length median:", int(statistics.median(lens)), "| max:", max(lens))
print("Chunks per section:", Counter(c["section"] for c in chunks).most_common())