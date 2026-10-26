import json
import random
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

MODEL = "BAAI/bge-small-en-v1.5"
N_LABELS = None
SHARD = 2000
OUT = Path("data/embeddings")
OUT.mkdir(parents=True, exist_ok=True)

with open("data/processed/labels.jsonl", encoding="utf-8") as f:
    set_ids = sorted({json.loads(line)["set_id"] for line in f})
random.seed(7)
keep = set(set_ids) if N_LABELS is None else set(random.sample(set_ids, N_LABELS))

chunks = []
with open("data/processed/chunks.jsonl", encoding="utf-8") as f:
    for line in f:
        c = json.loads(line)
        if c["set_id"] in keep:
            chunks.append(c)
print("Dev corpus:", len(keep), "labels,", len(chunks), "chunks")

with open("data/processed/dev_chunks.jsonl", "w", encoding="utf-8") as f:
    for c in chunks:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")

model = SentenceTransformer(MODEL)
for start in range(0, len(chunks), SHARD):
    path = OUT / f"shard_{start // SHARD:03d}.npy"
    if path.exists():
        print("skip", path.name)
        continue
    texts = [c["embed_text"] for c in chunks[start:start + SHARD]]
    vecs = model.encode(texts, batch_size=32, normalize_embeddings=True)
    np.save(path, vecs.astype(np.float32))
    print("saved", path.name, vecs.shape, flush=True)
print("Done")