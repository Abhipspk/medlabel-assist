import json
import time
from itertools import islice

from sentence_transformers import SentenceTransformer

MODEL = "BAAI/bge-small-en-v1.5"

with open("data/processed/chunks.jsonl", encoding="utf-8") as f:
    texts = [json.loads(line)["embed_text"] for line in islice(f, 500)]

model = SentenceTransformer(MODEL)
start = time.time()
vecs = model.encode(texts, batch_size=32, normalize_embeddings=True,
                    show_progress_bar=True)
secs = time.time() - start

print("Vector shape:", vecs.shape)
print(f"{secs:.1f}s for 500 chunks -> about {secs / 500 * 69305 / 60:.0f} min for all 69,305")