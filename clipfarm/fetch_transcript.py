"""Fetch SRT subtitle files for a movie/show title.

Tries the OpenSubtitles.com REST API first (v1). Falls back to
faster-whisper local transcription if no subtitle file is found
and the media file is available locally.

OpenSubtitles env vars (all optional — system still works without them
via the whisper fallback):
  OPENSUBTITLES_API_KEY
  OPENSUBTITLES_USER
  OPENSUBTITLES_PASS
"""

from __future__ import annotations
import os
import srt
import requests
from typing import Optional


_OPENSUBTITLES_BASE = "https://api.opensubtitles.com/api/v1"
_APP_NAME = "soundboardclipfarm"


def _os_headers(token: Optional[str] = None) -> dict:
    headers = {
        "Api-Key": os.environ.get("OPENSUBTITLES_API_KEY", ""),
        "Content-Type": "application/json",
        "User-Agent": _APP_NAME,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _os_login() -> Optional[str]:
    """Log in to OpenSubtitles and return the bearer token, or None."""
    user = os.environ.get("OPENSUBTITLES_USER", "")
    password = os.environ.get("OPENSUBTITLES_PASS", "")
    api_key = os.environ.get("OPENSUBTITLES_API_KEY", "")
    if not (user and password and api_key):
        return None
    try:
        resp = requests.post(
            f"{_OPENSUBTITLES_BASE}/login",
            json={"username": user, "password": password},
            headers=_os_headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("token")
    except Exception:
        return None


def fetch_srt_opensubtitles(title: str, language: str = "en") -> Optional[str]:
    """Return raw SRT text for `title` from OpenSubtitles, or None on miss."""
    token = _os_login()
    if not token:
        return None
    try:
        # Search for subtitles
        resp = requests.get(
            f"{_OPENSUBTITLES_BASE}/subtitles",
            params={"query": title, "languages": language, "type": "movie"},
            headers=_os_headers(token),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            return None
        file_id = data[0]["attributes"]["files"][0]["file_id"]

        # Request download link
        dl_resp = requests.post(
            f"{_OPENSUBTITLES_BASE}/download",
            json={"file_id": file_id},
            headers=_os_headers(token),
            timeout=15,
        )
        dl_resp.raise_for_status()
        link = dl_resp.json().get("link")
        if not link:
            return None

        # Download the SRT content
        srt_resp = requests.get(link, timeout=30)
        srt_resp.raise_for_status()
        return srt_resp.text
    except Exception:
        return None


def transcribe_with_whisper(media_path: str) -> Optional[str]:
    """Transcribe `media_path` with faster-whisper and return SRT text, or None."""
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(media_path, word_timestamps=True)
        subtitles = []
        for i, seg in enumerate(segments, start=1):
            subtitles.append(
                srt.Subtitle(
                    index=i,
                    start=srt.timedelta(seconds=seg.start),
                    end=srt.timedelta(seconds=seg.end),
                    content=seg.text.strip(),
                )
            )
        return srt.compose(subtitles)
    except ImportError:
        return None


def load_local_srt(srt_path: str) -> Optional[str]:
    """Load a user-provided SRT file."""
    try:
        with open(srt_path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def get_transcript(
    title: str,
    media_path: Optional[str] = None,
    local_srt: Optional[str] = None,
    language: str = "en",
) -> tuple[list[srt.Subtitle], str]:
    """Return parsed subtitles and the source used.

    Returns (subtitles, source) where source is one of:
    'opensubtitles', 'whisper', 'local_srt'.
    Raises RuntimeError if no transcript can be obtained.
    """
    if local_srt:
        raw = load_local_srt(local_srt)
        if raw:
            return list(srt.parse(raw)), "local_srt"

    raw = fetch_srt_opensubtitles(title, language)
    if raw:
        return list(srt.parse(raw)), "opensubtitles"

    if media_path:
        raw = transcribe_with_whisper(media_path)
        if raw:
            return list(srt.parse(raw)), "whisper"

    raise RuntimeError(
        f"Could not obtain transcript for '{title}'. "
        "Set OPENSUBTITLES_API_KEY/USER/PASS env vars, or pass --srt / --file."
    )
