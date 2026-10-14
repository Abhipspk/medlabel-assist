import argparse
import json
import re
from collections import defaultdict

import numpy as np
from qdrant_client import QdrantClient, models
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
PREFIX = "Represent this sentence for searching relevant passages: "
SKIP_WORDS = {"sodium", "potassium", "calcium", "magnesium", "and", "the",
              "extended", "release", "delayed", "tablet", "tablets"}
ALL_SECTIONS = ["contraindications", "boxed_warning", "warnings", "drug_interactions",
                "adverse_reactions", "dosage_and_administration",
                "indications_and_usage", "use_in_specific_populations", "overdosage"]


def tok(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def drug_key(generic_name):
    """First meaningful word of the generic name, e.g. 'METFORMIN HYDROCHLORIDE' -> 'metformin'."""
    for w in re.findall(r"[a-z]+", generic_name.lower()):
        if w not in SKIP_WORDS:
            return w
    return ""


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
        self.drugs = defaultdict(set)          # drug key -> exact generic names
        for c in self.chunks:
            self.drugs[drug_key(c["generic_name"])].add(c["generic_name"])
        self.drugs.pop("", None)
        self.alias = {}                        # brand-name word -> drug key
        for c in self.chunks:
            b, g = drug_key(c["brand_name"]), drug_key(c["generic_name"])
            if b and g and b != g and b not in self.drugs:
                self.alias[b] = g

    def detect_drug(self, question):
        for w in re.findall(r"[a-z]+", question.lower()):
            if len(w) >= 4:
                if w in self.drugs:
                    return w
                if w in self.alias:
                    return self.alias[w]
        return None

    def _dense(self, query, k, sections, drug):
        must = []
        if sections:
            must.append(models.FieldCondition(
                key="section", match=models.MatchAny(any=list(sections))))
        if drug:
            must.append(models.FieldCondition(
                key="generic_name", match=models.MatchAny(any=sorted(self.drugs[drug]))))
        flt = models.Filter(must=must) if must else None
        vec = self.embedder.encode(PREFIX + query, normalize_embeddings=True).tolist()
        hits = self.client.query_points("labels", query=vec, query_filter=flt, limit=k)
        return [h.id for h in hits.points]

    def _sparse(self, query, k, sections, drug):
        scores = self.bm25.get_scores(tok(query))
        if sections or drug:
            allowed_s = set(sections) if sections else None
            allowed_d = self.drugs[drug] if drug else None
            mask = np.array([
                (allowed_s is None or c["section"] in allowed_s)
                and (allowed_d is None or c["generic_name"] in allowed_d)
                for c in self.chunks])
            scores = np.where(mask, scores, -1.0)
        order = np.argsort(scores)[::-1][:k]
        return [int(i) for i in order if scores[i] > 0]

    def search(self, query, top_k=5, candidates=20, sections=None, drug=None, rerank=True):
        fused = rrf([self._dense(query, candidates, sections, drug),
                     self._sparse(query, candidates, sections, drug)])[:candidates]
        if not fused:
            return []
        if not rerank:
            return [{**self.chunks[i], "score": None} for i in fused[:top_k]]
        pairs = [(query, self.chunks[i]["embed_text"]) for i in fused]
        scores = self.reranker.predict(pairs)
        order = np.argsort(scores)[::-1][:top_k]
        return [{**self.chunks[fused[j]], "score": float(scores[j])} for j in order]

    def search_by_section(self, query, sections, per_section=3, candidates=10,
                          drug=None, rerank=True):
        """Search each routed section separately so every section gets candidates."""
        hits = []
        for sec in sections:
            hits.extend(self.search(query, top_k=per_section, candidates=candidates,
                                    sections=[sec], drug=drug, rerank=rerank))
        return hits

    def search_diverse(self, query, per_section=1, candidates=10, drug=None, top_k=4):
        """No router needed: best chunk from every section, then keep the top_k by score."""
        hits = self.search_by_section(query, ALL_SECTIONS, per_section=per_section,
                                      candidates=candidates, drug=drug, rerank=True)
        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits[:top_k]

    def close(self):
        self.client.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--sections", default=None, help="comma-separated section names")
    ap.add_argument("--drug", default=None, help="drug key, e.g. metformin")
    ap.add_argument("--no-rerank", action="store_true")
    args = ap.parse_args()
    secs = args.sections.split(",") if args.sections else None
    r = Retriever()
    try:
        for hit in r.search(args.query, sections=secs, drug=args.drug, rerank=not args.no_rerank):
            print(f"[{hit['score']}] {hit['generic_name'][:30]} | {hit['manufacturer'][:25]} | "
                  f"{hit['section']}\n    {hit['text'][:160]}")
    finally:
        r.close()