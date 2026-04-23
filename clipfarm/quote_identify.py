"""Quote identification — find where a quote is from with no title provided.

Two-stage strategy:
1. GetYarn search (returns a direct clip + source info — fastest path)
2. OpenSubtitles full-text search (identifies title from phrase, no clip)

Returns a QuoteIdentification with the discovered title and optional
pre-fetched media path so the calling pipeline can skip sourcing entirely
when GetYarn already has the clip.
"""

from __future__ import annotations
import os
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class QuoteIdentification:
    title: str                     # identified movie or show title
    media_path: Optional[str]      # pre-fetched clip path (GetYarn), or None
    provider: str                  # which source identified it
    confidence: float              # 0.0–1.0


def identify(quote: str, language: str = "en") -> QuoteIdentification:
    """Identify the source of a quote.

    Tries GetYarn first (returns clip directly), then OpenSubtitles text search.
    Raises RuntimeError if no source can identify the quote.
    """
    # Strategy 1: GetYarn — quote-indexed clips, returns source title + clip
    result = _try_getyarn(quote)
    if result:
        return result

    # Strategy 2: OpenSubtitles full-text subtitle search
    result = _try_opensubtitles(quote, language)
    if result:
        return result

    raise RuntimeError(
        f"Could not identify the source of quote: '{quote}'. "
        "Try entering the movie or show title manually."
    )


def _try_getyarn(quote: str) -> Optional[QuoteIdentification]:
    """Search GetYarn by quote text. Returns identification with pre-fetched clip."""
    try:
        import requests
        import tempfile

        resp = requests.get(
            "https://getyarn.io/yarn-clip/find",
            params={"text": quote, "limit": 3},
            headers={"User-Agent": "Mozilla/5.0 (compatible; soundboardclipfarm/1.0)"},
            timeout=15,
        )
        resp.raise_for_status()

        # Try JSON first
        title = None
        clip_id = None
        if "application/json" in resp.headers.get("content-type", ""):
            data = resp.json()
            clips = data.get("clips") or data.get("data") or []
            if clips:
                clip_id = clips[0].get("uuid") or clips[0].get("id")
                title = (
                    clips[0].get("show") or clips[0].get("title") or
                    clips[0].get("video", {}).get("title", "")
                )
        else:
            # HTML scraping fallback
            ids = re.findall(r'yarn-clip/([a-f0-9-]{36})', resp.text)
            # Try to extract title from HTML meta or title tags
            title_match = re.search(r'<title[^>]*>([^<]+)</title>', resp.text, re.IGNORECASE)
            if title_match:
                raw = title_match.group(1)
                # GetYarn titles often look like "Quote - Show Name | GetYarn"
                title = _clean_getyarn_title(raw)
            clip_id = ids[0] if ids else None

        if not clip_id:
            return None

        # Download the clip
        clip_url = f"https://y.yarn.co/{clip_id}.mp4"
        out_dir = tempfile.mkdtemp(prefix="clipfarm_yarn_id_")
        out_path = os.path.join(out_dir, f"{clip_id}.mp4")

        dl = requests.get(
            clip_url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; soundboardclipfarm/1.0)"},
            stream=True, timeout=30,
        )
        dl.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in dl.iter_content(8192):
                f.write(chunk)

        return QuoteIdentification(
            title=title or "Unknown (via GetYarn)",
            media_path=out_path,
            provider="getyarn",
            confidence=0.9,
        )
    except Exception:
        return None


def _try_opensubtitles(quote: str, language: str) -> Optional[QuoteIdentification]:
    """Search OpenSubtitles for a subtitle phrase. Returns title only (no clip)."""
    try:
        import requests

        api_key = os.environ.get("OPENSUBTITLES_API_KEY", "")
        if not api_key:
            return None

        user = os.environ.get("OPENSUBTITLES_USER", "")
        password = os.environ.get("OPENSUBTITLES_PASS", "")

        _OS_BASE = "https://api.opensubtitles.com/api/v1"
        headers = {"Api-Key": api_key, "Content-Type": "application/json", "User-Agent": "soundboardclipfarm"}

        # Login
        login = requests.post(f"{_OS_BASE}/login", json={"username": user, "password": password},
                              headers=headers, timeout=15)
        token = login.json().get("token") if login.ok else None
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # Search by subtitle text
        resp = requests.get(
            f"{_OS_BASE}/subtitles",
            params={"query": quote, "languages": language},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("data", [])
        if not items:
            return None

        attrs = items[0].get("attributes", {})
        title = (
            attrs.get("feature_details", {}).get("title") or
            attrs.get("feature_details", {}).get("movie_name") or
            attrs.get("release", "")
        )
        if not title:
            return None

        return QuoteIdentification(
            title=title,
            media_path=None,
            provider="opensubtitles_identify",
            confidence=0.7,
        )
    except Exception:
        return None


def _clean_getyarn_title(raw: str) -> str:
    """Extract a clean show/movie name from a GetYarn page title."""
    # Pattern: "Quote text - Show Name | GetYarn.io" or similar
    raw = re.sub(r'\s*\|\s*GetYarn.*$', '', raw, flags=re.IGNORECASE).strip()
    parts = raw.split(' - ')
    if len(parts) >= 2:
        return parts[-1].strip()
    return raw.strip()
