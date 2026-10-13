import argparse
import json
import re

import numpy as np
from qdrant_client import QdrantClient, models
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
PREFIX = "Represent this sentence for searching relevant passages: "


def tok(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def rrf(rank_lists, k=60):
    scores = {}
    for lst in rank_lists:
        for rank, i in enumerate(lst):
            scores[i] = scores.get(i, 0) + 1 / (k + rank + 1)
    return sorted(scores, key=scores.get, reverse=True)


class Retriever:
    def __init__(self, chunks_path="data/processed/dev_chunks.jsonl",
                 qdrant_path="data/qdrant"):
        with open(chunks_path, encoding="utf-8") as f:
            self.chunks = [json.loads(line) for line in f]
        self.bm25 = BM25Okapi([tok(c["embed_text"]) for c in self.chunks])
        self.embedder = SentenceTransformer(EMBED_MODEL)
        self.reranker = CrossEncoder(RERANK_MODEL)
        self.client = QdrantClient(path=qdrant_path)

    def _dense(self, query, k, section):
        flt = None
        if section:
            flt = models.Filter(must=[models.FieldCondition(
                key="section", match=models.MatchValue(value=section))])
        vec = self.embedder.encode(PREFIX + query, normalize_embeddings=True).tolist()
        hits = self.client.query_points("labels", query=vec, query_filter=flt, limit=k)
        return [h.id for h in hits.points]

    def _sparse(self, query, k, section):
        scores = self.bm25.get_scores(tok(query))
        if section:
            mask = np.array([c["section"] == section for c in self.chunks])
            scores = np.where(mask, scores, -1.0)
        order = np.argsort(scores)[::-1][:k]
        return [int(i) for i in order if scores[i] > 0]

    def search(self, query, top_k=5, candidates=20, section=None, rerank=True):
        fused = rrf([self._dense(query, candidates, section),
                     self._sparse(query, candidates, section)])[:candidates]
        if not fused:
            return []
        if not rerank:
            return [{**self.chunks[i], "score": None} for i in fused[:top_k]]
        pairs = [(query, self.chunks[i]["embed_text"]) for i in fused]
        scores = self.reranker.predict(pairs)
        order = np.argsort(scores)[::-1][:top_k]
        return [{**self.chunks[fused[j]], "score": float(scores[j])} for j in order]

    def close(self):
        self.client.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--section", default=None)
    ap.add_argument("--no-rerank", action="store_true")
    args = ap.parse_args()
    r = Retriever()
    for hit in r.search(args.query, section=args.section, rerank=not args.no_rerank):
        print(f"[{hit['score']}] {hit['generic_name'][:30]} | {hit['manufacturer'][:25]} | "
              f"{hit['section']}\n    {hit['text'][:160]}")
    r.close()