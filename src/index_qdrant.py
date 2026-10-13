import json
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient, models

with open("data/processed/dev_chunks.jsonl", encoding="utf-8") as f:
    chunks = [json.loads(line) for line in f]
vectors = np.vstack([np.load(p) for p in sorted(Path("data/embeddings").glob("shard_*.npy"))])
assert len(chunks) == len(vectors), (len(chunks), len(vectors))

client = QdrantClient(path="data/qdrant")
if client.collection_exists("labels"):
    client.delete_collection("labels")
client.create_collection(
    "labels",
    vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE),
)
points = (
    models.PointStruct(id=i, vector=vectors[i].tolist(), payload=chunks[i])
    for i in range(len(chunks))
)
client.upload_points("labels", points, batch_size=256)
print("Indexed:", client.count("labels").count)
client.close()