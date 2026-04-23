"""Preflight request classifier — gate before sourcing begins.

Returns a PreflightResult with a stable decision enum plus separate 
user-facing message and internal diagnostic reason.

Decision states:
  ready                — proceed to sourcing
  needs_local_file     — auto-discovery unlikely to succeed; local file recommended
  needs_episode_scope  — TV series without episode context; result would be ambiguous
  unsupported_discovery — no viable sourcing path for this request shape
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Literal, Optional

PreflightDecision = Literal[
    "ready",                  # proceed to sourcing
    "needs_local_file",       # local file strongly recommended; will warn but allow
    "needs_episode_scope",    # TV series without episode context; ambiguous result
    "unsupported_discovery",  # no viable sourcing path exists for this shape
]


@dataclass
class PreflightResult:
    decision: PreflightDecision
    user_message: str         # product-language copy for the UI — no internals
    diagnostic_reason: str    # internal explanation for job record / debugging
    blocking: bool            # True = do not proceed; False = warn but allow


def check(
    title: str,
    quote: str,
    local_file: Optional[str] = None,
    local_srt: Optional[str] = None,
    media_type: Optional[str] = None,     # "movie" | "tv_series" | None (unknown)
    series: Optional[str] = None,
    season: Optional[int] = None,
    episode: Optional[int] = None,
) -> PreflightResult:
    """Classify the request and return a preflight decision.        

    Does not make network calls. Works from request fields only.    
    """
    has_local_file = bool(local_file and local_file.strip())        
    is_tv = media_type == "tv_series" or _looks_like_tv_series(title)
    has_episode_scope = (season is not None) or (episode is not None) or has_local_file

    # Rule 1: TV series with no episode scope and no local file     
    # (Non-blocking: warn and attempt discovery, but local file is better)
    if is_tv and not has_episode_scope:
        return PreflightResult(
            decision="needs_episode_scope",
            user_message=(
                f"'{title}' looks like a TV series. "
                "Since TV quotes can appear across many episodes, auto-discovery is difficult. "
                "We will try to find a match, but for the best results, please specify a season/episode "
                "or upload the specific media file you have."
            ),
            diagnostic_reason=(
                f"media_type={'tv_series' if media_type == 'tv_series' else 'inferred_tv'}; "
                f"no season/episode/local_file provided; quote '{quote}' is ambiguous across episodes"
            ),
            blocking=False, # CHANGED: No longer blocking.
        )

    # Rule 2: High-risk commercial content (No local file)
    # We use a broad heuristic: any title that isn't explicitly public domain-era 
    # (pre-1928) or Creative Commons usually requires a local file.
    if not has_local_file:
        # Check if it's a known restricted title/franchise (as a secondary heuristic)
        if _is_mainstream_restricted(title):
            return PreflightResult(
                decision="needs_local_file",
                user_message=(
                    f"'{title}' is a major commercial title. "
                    "Automated discovery will likely fail due to licensing restrictions. "
                    "For reliable results, we strongly recommend uploading your own media file."
                ),
                diagnostic_reason=(
                    f"title '{title}' matched high-risk commercial keywords; "
                    "auto-discovery is low-confidence per authorized-source policy"
                ),
                blocking=False, 
            )

        # General "no local file" warning
        return PreflightResult(
            decision="needs_local_file",
            user_message=(
                "No media file provided. Auto-discovery will try public domain and CC-licensed sources, "
                "but usually fails for commercial movies or shows. "
                "Uploading your own file is the most reliable way to extract a clip."
            ),
            diagnostic_reason=(
                "local_file=None; auto-discovery path selected; "
                "mainstream commercial content is unlikely to resolve via authorized discovery"
            ),
            blocking=False,
        )

    # Rule 3: Local file provided — ready
    return PreflightResult(
        decision="ready",
        user_message="",
        diagnostic_reason=f"local_file provided: {local_file}",     
        blocking=False,
    )


# ── Heuristics ────────────────────────────────────────────────────────────────

_TV_KEYWORDS = {
    "season", "episode", "series", "show", "pilot", "finale",       
    "s01", "s02", "s03", "s04", "s05", "s06", "s07", "s08",
    "e01", "e02", "ep1", "ep2",
}

# Structural signal for mainstream franchises or studios that are strictly protected
_MAINSTREAM_KEYWORDS = {
    "disney", "marvel", "mcu", "star wars", "pixar", "dreamworks",
    "warner", "hbo", "netflix", "universal", "paramount", "columbia",
    "the office", "friends", "seinfeld", "breaking bad", "game of thrones"
}

_TV_PATTERNS = [
    re.compile(r'\bs\d{1,2}e\d{1,2}\b', re.IGNORECASE),   # S01E03  
    re.compile(r'\bseason\s+\d+\b', re.IGNORECASE),        # Season 2
    re.compile(r'\bepisode\s+\d+\b', re.IGNORECASE),       # Episode 5
]


def _looks_like_tv_series(title: str) -> bool:
    """Structural heuristic — detects TV formatting signals."""
    t = title.lower()
    if any(kw in t.split() for kw in _TV_KEYWORDS):
        return True
    if any(p.search(title) for p in _TV_PATTERNS):
        return True
    return False

def _is_mainstream_restricted(title: str) -> bool:
    """Heuristic for common commercial titles that typically require local files."""
    t = title.lower()
    return any(kw in t for kw in _MAINSTREAM_KEYWORDS)
