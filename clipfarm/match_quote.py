"""Match a user-supplied quote against parsed SRT subtitles.

Uses rapidfuzz for fuzzy matching. Merges adjacent subtitle lines when
the quote spans a line boundary.
"""

from __future__ import annotations
import re
import srt
from rapidfuzz import fuzz, process
from typing import Optional
from .models import QuoteMatch


_MIN_CONFIDENCE = 0.60   # reject matches below this threshold
_MAX_CLIP_SECONDS = 14.5  # hard cap; leaves headroom under the 15s limit


def _normalize_text(text: str) -> str:
    """Lowercase and strip punctuation for stable matching."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return text.strip()


def _srt_line_text(sub: srt.Subtitle) -> str:
    return sub.content.replace("\n", " ").strip()


def _merge_window(
    subs: list[srt.Subtitle], start_idx: int, end_idx: int
) -> tuple[float, float, str]:
    """Return (start_sec, end_sec, merged_text) for subs[start_idx:end_idx+1]."""
    window = subs[start_idx : end_idx + 1]
    text = " ".join(_srt_line_text(s) for s in window)
    start_sec = window[0].start.total_seconds()
    end_sec = window[-1].end.total_seconds()
    return start_sec, end_sec, text


def find_quote(
    quote: str,
    subtitles: list[srt.Subtitle],
    subtitle_source: str,
    window_size: int = 3,
) -> QuoteMatch:
    """Find the best-matching position in `subtitles` for `quote`.

    Tries single-line matches first, then sliding windows of up to
    `window_size` consecutive lines for multi-line quotes.

    Raises ValueError if no match meets the confidence threshold.
    """
    candidates: list[tuple[float, float, str, float]] = []  # (start, end, text, score)

    norm_quote = _normalize_text(quote)
    lines = [_srt_line_text(s) for s in subtitles]
    norm_lines = [_normalize_text(l) for l in lines]

    # Single-line pass
    results = process.extract(
        norm_quote, norm_lines, scorer=fuzz.token_set_ratio, limit=10
    )
    for matched_norm_text, score, idx in results:
        norm_score = score / 100.0
        if norm_score < _MIN_CONFIDENCE:
            continue
        start_sec = subtitles[idx].start.total_seconds()
        end_sec = subtitles[idx].end.total_seconds()
        duration = end_sec - start_sec
        if duration <= _MAX_CLIP_SECONDS:
            # We keep the original (not normalized) text for the result
            candidates.append((start_sec, end_sec, lines[idx], norm_score))

    # Multi-line sliding window pass
    for size in range(2, window_size + 1):
        for i in range(len(subtitles) - size + 1):
            start_sec, end_sec, merged = _merge_window(subtitles, i, i + size - 1)
            if (end_sec - start_sec) > _MAX_CLIP_SECONDS:
                continue
            norm_merged = _normalize_text(merged)
            score = fuzz.token_sort_ratio(norm_quote, norm_merged) / 100.0
            if score >= _MIN_CONFIDENCE:
                candidates.append((start_sec, end_sec, merged, score))

    if not candidates:
        raise ValueError(
            f"No subtitle match found for quote: '{quote}' "
            f"(minimum confidence: {_MIN_CONFIDENCE})"
        )

    best = max(candidates, key=lambda c: c[3])
    start_sec, end_sec, matched_text, confidence = best

    return QuoteMatch(
        quote_text=quote,
        matched_text=matched_text,
        match_confidence=confidence,
        start_time=start_sec,
        end_time=end_sec,
        subtitle_source=subtitle_source,  # type: ignore[arg-type]
    )
