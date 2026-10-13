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

    def _dense(self, query, k, sections):
        flt = None
        if sections:
            flt = models.Filter(must=[models.FieldCondition(
                key="section", match=models.MatchAny(any=list(sections)))])
        vec = self.embedder.encode(PREFIX + query, normalize_embeddings=True).tolist()
        hits = self.client.query_points("labels", query=vec, query_filter=flt, limit=k)
        return [h.id for h in hits.points]

    def _sparse(self, query, k, sections):
        scores = self.bm25.get_scores(tok(query))
        if sections:
            allowed = set(sections)
            mask = np.array([c["section"] in allowed for c in self.chunks])
            scores = np.where(mask, scores, -1.0)
        order = np.argsort(scores)[::-1][:k]
        return [int(i) for i in order if scores[i] > 0]

    def search(self, query, top_k=5, candidates=20, sections=None, rerank=True):
        fused = rrf([self._dense(query, candidates, sections),
                     self._sparse(query, candidates, sections)])[:candidates]
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
    ap.add_argument("--sections", default=None, help="comma-separated section names")
    ap.add_argument("--no-rerank", action="store_true")
    args = ap.parse_args()
    secs = args.sections.split(",") if args.sections else None
    r = Retriever()
    try:
        for hit in r.search(args.query, sections=secs, rerank=not args.no_rerank):
            print(f"[{hit['score']}] {hit['generic_name'][:30]} | {hit['manufacturer'][:25]} | "
                  f"{hit['section']}\n    {hit['text'][:160]}")
    finally:
        r.close()