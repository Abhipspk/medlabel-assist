import json
import re
import sys

import numpy as np
from qdrant_client import QdrantClient
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

with open("data/processed/dev_chunks.jsonl", encoding="utf-8") as f:
    chunks = [json.loads(line) for line in f]

if sys.argv[1:] == ["--drugs"]:
    names = sorted({c["generic_name"][:50] for c in chunks})
    print(len(names), "distinct generic names. Sample:")
    for n in names[::max(1, len(names) // 40)]:
        print(" ", n)
    sys.exit()

query = " ".join(sys.argv[1:])
PREFIX = "Represent this sentence for searching relevant passages: "


def tok(text):
    return re.findall(r"[a-z0-9]+", text.lower())


bm25 = BM25Okapi([tok(c["embed_text"]) for c in chunks])
model = SentenceTransformer("BAAI/bge-small-en-v1.5")
client = QdrantClient(path="data/qdrant")


def dense(q, k=20):
    v = model.encode(PREFIX + q, normalize_embeddings=True).tolist()
    return [h.id for h in client.query_points("labels", query=v, limit=k).points]


def sparse(q, k=20):
    return [int(i) for i in np.argsort(bm25.get_scores(tok(q)))[::-1][:k]]


def rrf(rank_lists, k=60):
    scores = {}
    for lst in rank_lists:
        for rank, i in enumerate(lst):
            scores[i] = scores.get(i, 0) + 1 / (k + rank + 1)
    return sorted(scores, key=scores.get, reverse=True)


def show(label, ids):
    print(f"\n{label}")
    for i in ids[:3]:
        c = chunks[i]
        print(f"  {c['generic_name'][:30]} | {c['section']} | {c['text'][:110]}")


d, s = dense(query), sparse(query)
print("QUERY:", query)
show("DENSE (meaning)", d)
show("BM25 (keywords)", s)
show("HYBRID (RRF)", rrf([d, s]))
client.close()