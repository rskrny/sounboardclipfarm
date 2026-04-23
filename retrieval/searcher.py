"""
Hybrid search engine.

Combines BM25 (lexical) and semantic (vector) retrieval
using Reciprocal Rank Fusion for stable, high-quality results.
"""

import re
from typing import Optional
from dataclasses import dataclass

from .config import RetrievalConfig
from .store import Store


@dataclass
class SearchResult:
    """A single search result with score and metadata."""

    chunk_id: int
    text: str
    source_file: str
    header_path: list[str]
    domain: Optional[str]
    tags: list[str]
    score: float
    bm25_rank: Optional[int] = None
    semantic_rank: Optional[int] = None

    @property
    def context_label(self) -> str:
        parts = [self.source_file]
        if self.header_path:
            parts.append(" > ".join(self.header_path))
        return " | ".join(parts)


def _tokenize(text: str) -> list[str]:
    """Match the tokenizer used at index time."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return [t for t in text.split() if len(t) > 1]


def _reciprocal_rank_fusion(
    ranked_lists: list[list[int]],
    weights: list[float],
    k: int = 60,
) -> list[tuple[int, float]]:
    """
    Combine multiple ranked lists using Reciprocal Rank Fusion.

    RRF score = sum(weight_i / (k + rank_i)) for each list i.
    Higher k smooths differences between top and bottom ranks.

    Returns list of (chunk_id, fused_score) sorted by score descending.
    """
    scores: dict[int, float] = {}

    for ranked_list, weight in zip(ranked_lists, weights):
        for rank, chunk_id in enumerate(ranked_list):
            if chunk_id not in scores:
                scores[chunk_id] = 0.0
            scores[chunk_id] += weight / (k + rank + 1)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


class Searcher:
    """Hybrid BM25 + semantic search with reciprocal rank fusion."""

    def __init__(self, config: RetrievalConfig):
        self.config = config
        self.store = Store(config.db_path, config.store_dir)
        self.bm25 = self.store.load_bm25()
        self.embeddings = None
        self.model = None
        self._chunks = None

        if config.use_semantic:
            self.embeddings = self.store.load_embeddings()

    @property
    def chunks(self) -> list[dict]:
        if self._chunks is None:
            self._chunks = self.store.get_all_chunks()
        return self._chunks

    def _get_semantic_model(self):
        """Lazy-load the embedding model (only when needed for queries)."""
        if self.model is None:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.config.embedding_model)
        return self.model

    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        domain_filter: Optional[str] = None,
        file_filter: Optional[str] = None,
    ) -> list[SearchResult]:
        """
        Run hybrid search.

        Args:
            query: Natural language search query
            top_k: Number of results to return
            domain_filter: Only return results from this domain
            file_filter: Only return results from files matching this substring

        Returns:
            List of SearchResult sorted by relevance
        """
        if top_k is None:
            top_k = self.config.default_top_k

        chunks = self.chunks
        if not chunks:
            return []

        # Build chunk_id to index mapping
        id_to_idx = {c["id"]: i for i, c in enumerate(chunks)}
        rerank_n = self.config.rerank_top_n

        # BM25 retrieval
        bm25_ranked = self._bm25_search(query, rerank_n)

        ranked_lists = [bm25_ranked]
        weights = [self.config.bm25_weight]

        # Semantic retrieval
        if self.config.use_semantic and self.embeddings is not None:
            semantic_ranked = self._semantic_search(query, rerank_n)
            ranked_lists.append(semantic_ranked)
            weights.append(self.config.semantic_weight)

        # Fuse
        fused = _reciprocal_rank_fusion(ranked_lists, weights)

        # Build results with rank info
        bm25_rank_map = {cid: rank for rank, cid in enumerate(bm25_ranked)}
        semantic_rank_map = {}
        if len(ranked_lists) > 1:
            semantic_rank_map = {cid: rank for rank, cid in enumerate(ranked_lists[1])}

        results = []
        for chunk_id, score in fused:
            if chunk_id not in id_to_idx:
                continue
            chunk = chunks[id_to_idx[chunk_id]]

            # Apply filters
            if domain_filter and chunk["domain"] != domain_filter:
                continue
            if file_filter and file_filter not in chunk["source_file"]:
                continue

            results.append(SearchResult(
                chunk_id=chunk_id,
                text=chunk["text"],
                source_file=chunk["source_file"],
                header_path=chunk["header_path"],
                domain=chunk["domain"],
                tags=chunk["tags"],
                score=score,
                bm25_rank=bm25_rank_map.get(chunk_id),
                semantic_rank=semantic_rank_map.get(chunk_id),
            ))

            if len(results) >= top_k:
                break

        return results

    def _bm25_search(self, query: str, top_n: int) -> list[int]:
        """Return chunk IDs ranked by BM25 score."""
        tokens = _tokenize(query)
        if not tokens or self.bm25 is None:
            return []

        scores = self.bm25.get_scores(tokens)
        chunks = self.chunks

        # Get top N indices
        ranked_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )[:top_n]

        return [chunks[i]["id"] for i in ranked_indices if scores[i] > 0]

    def _semantic_search(self, query: str, top_n: int) -> list[int]:
        """Return chunk IDs ranked by cosine similarity."""
        import numpy as np

        if self.embeddings is None:
            return []

        model = self._get_semantic_model()
        query_emb = model.encode([query], normalize_embeddings=True)[0]

        # Cosine similarity (embeddings already normalized)
        similarities = np.dot(self.embeddings, query_emb)

        ranked_indices = np.argsort(similarities)[::-1][:top_n]
        chunks = self.chunks

        return [
            chunks[i]["id"]
            for i in ranked_indices
            if similarities[i] > 0.1  # minimum threshold
        ]

    def search_bm25_only(
        self,
        query: str,
        top_k: Optional[int] = None,
    ) -> list[SearchResult]:
        """BM25-only search. No ML dependencies needed."""
        if top_k is None:
            top_k = self.config.default_top_k

        ranked_ids = self._bm25_search(query, top_k)
        chunks_by_id = {c["id"]: c for c in self.chunks}

        results = []
        for rank, chunk_id in enumerate(ranked_ids[:top_k]):
            chunk = chunks_by_id.get(chunk_id)
            if chunk is None:
                continue
            results.append(SearchResult(
                chunk_id=chunk_id,
                text=chunk["text"],
                source_file=chunk["source_file"],
                header_path=chunk["header_path"],
                domain=chunk["domain"],
                tags=chunk["tags"],
                score=1.0 / (60 + rank + 1),
                bm25_rank=rank,
            ))
        return results

    def get_stats(self) -> dict:
        return {
            "total_chunks": len(self.chunks),
            "domains": self.store.list_domains(),
            "files": self.store.list_source_files(),
            "bm25_loaded": self.bm25 is not None,
            "semantic_loaded": self.embeddings is not None,
            "last_indexed": self.store.get_meta("last_indexed"),
        }

    def close(self):
        self.store.close()
