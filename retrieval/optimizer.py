"""
Token budget optimizer.

Applies information-theoretic principles to maximize the signal-to-noise
ratio of retrieved context within a fixed token budget.

Three strategies:
1. Information density ranking -- prefer chunks with more unique concepts per token
2. Redundancy elimination -- MMR-style diversity to avoid repetition
3. Context compression -- trim boilerplate while preserving meaning
"""

import re
import math
from collections import Counter
from typing import Optional

from .searcher import SearchResult


def _estimate_information_density(text: str) -> float:
    """
    Approximate information density using vocabulary richness.

    Higher = more unique concepts per token.
    Based on type-token ratio (TTR) with length normalization.
    """
    words = re.findall(r"\b\w+\b", text.lower())
    if len(words) < 5:
        return 0.0

    types = len(set(words))
    tokens = len(words)

    # Root TTR (Guiraud's index) -- normalized for length
    ttr = types / math.sqrt(tokens)

    # Penalize very short chunks (less context)
    length_bonus = min(1.0, tokens / 50)

    return ttr * length_bonus


def _compute_overlap(text_a: str, text_b: str) -> float:
    """
    Compute token-level Jaccard overlap between two texts.
    Returns 0.0 (no overlap) to 1.0 (identical).
    """
    words_a = set(re.findall(r"\b\w+\b", text_a.lower()))
    words_b = set(re.findall(r"\b\w+\b", text_b.lower()))

    if not words_a or not words_b:
        return 0.0

    intersection = len(words_a & words_b)
    union = len(words_a | words_b)
    return intersection / union


def _compress_chunk(text: str) -> str:
    """
    Light compression: remove boilerplate without losing meaning.

    Strips:
    - Repeated whitespace
    - HTML comments
    - Markdown link URLs (keep link text)
    - Empty list items
    - Redundant formatting markers
    """
    # Remove HTML comments
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

    # Simplify markdown links: [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Remove image references: ![alt](url)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)

    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove trailing whitespace on lines
    text = re.sub(r" +$", "", text, flags=re.MULTILINE)

    return text.strip()


def optimize_context(
    results: list[SearchResult],
    token_budget: int = 4000,
    diversity_lambda: float = 0.7,
    compress: bool = True,
    min_density: float = 0.0,
) -> list[dict]:
    """
    Select and optimize chunks to maximize information value within a token budget.

    Implements Maximal Marginal Relevance (MMR) with information density weighting:
    1. Score each candidate by: relevance * density * diversity
    2. Greedily select the highest-scoring candidate
    3. Recompute diversity penalties for remaining candidates
    4. Stop when token budget is exhausted

    Args:
        results: Ranked search results from the searcher
        token_budget: Maximum tokens in the output context
        diversity_lambda: 0.0 = max diversity, 1.0 = max relevance (default: 0.7)
        compress: Whether to apply light compression to reduce token waste
        min_density: Minimum information density threshold (filter out fluff)

    Returns:
        List of dicts with 'text', 'source', 'score', 'tokens', 'density'
    """
    if not results:
        return []

    # Prepare candidates with density scores
    candidates = []
    for r in results:
        density = _estimate_information_density(r.text)
        if density < min_density:
            continue

        text = _compress_chunk(r.text) if compress else r.text
        tokens = len(text) // 4

        candidates.append({
            "result": r,
            "text": text,
            "tokens": tokens,
            "density": density,
            "relevance": r.score,
            "selected": False,
        })

    if not candidates:
        return []

    # Normalize relevance scores to [0, 1]
    max_rel = max(c["relevance"] for c in candidates)
    if max_rel > 0:
        for c in candidates:
            c["relevance"] /= max_rel

    # Normalize density scores to [0, 1]
    max_den = max(c["density"] for c in candidates)
    if max_den > 0:
        for c in candidates:
            c["density"] /= max_den

    # MMR selection
    selected = []
    tokens_used = 0

    while candidates and tokens_used < token_budget:
        best_score = -1
        best_idx = -1

        for i, cand in enumerate(candidates):
            if cand["selected"]:
                continue

            # Would this exceed budget?
            if tokens_used + cand["tokens"] > token_budget:
                continue

            # Relevance component (weighted by density)
            rel_score = cand["relevance"] * (0.5 + 0.5 * cand["density"])

            # Diversity component: max overlap with any selected chunk
            max_overlap = 0.0
            for sel in selected:
                overlap = _compute_overlap(cand["text"], sel["text"])
                max_overlap = max(max_overlap, overlap)

            # MMR score
            mmr = diversity_lambda * rel_score - (1 - diversity_lambda) * max_overlap

            if mmr > best_score:
                best_score = mmr
                best_idx = i

        if best_idx < 0:
            break

        cand = candidates[best_idx]
        cand["selected"] = True

        selected.append({
            "text": cand["text"],
            "source": cand["result"].context_label,
            "source_file": cand["result"].source_file,
            "score": round(cand["relevance"] * max_rel, 4),
            "tokens": cand["tokens"],
            "density": round(cand["density"] * max_den, 4),
        })
        tokens_used += cand["tokens"]

    return selected


def format_context_block(
    optimized: list[dict],
    include_sources: bool = True,
) -> str:
    """
    Format optimized chunks into a single context block for LLM injection.

    Returns a string ready to be inserted into a prompt.
    """
    if not optimized:
        return ""

    parts = []
    total_tokens = 0

    for item in optimized:
        if include_sources:
            parts.append(f"[Source: {item['source']}]\n{item['text']}")
        else:
            parts.append(item["text"])
        total_tokens += item["tokens"]

    header = f"--- Retrieved Context ({total_tokens} tokens, {len(optimized)} chunks) ---"
    footer = "--- End Retrieved Context ---"

    return f"{header}\n\n" + "\n\n---\n\n".join(parts) + f"\n\n{footer}"
