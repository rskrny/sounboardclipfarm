"""Fetch SRT subtitle files for a movie/show title.

Tries OpenSubtitles API first. Falls back to faster-whisper transcription
if no subtitle file is found and the media file is available locally.
"""

from __future__ import annotations
import os
import srt
from typing import Optional
from .models import QuoteMatch


def fetch_srt_opensubtitles(title: str, language: str = "en") -> Optional[str]:
    """Return raw SRT text for `title` from OpenSubtitles, or None on miss."""
    try:
        from opensubtitlesapi import OpenSubtitles
        api_key = os.environ.get("OPENSUBTITLES_API_KEY", "")
        if not api_key:
            return None
        client = OpenSubtitles("soundboardclipfarm", api_key)
        client.login(
            os.environ.get("OPENSUBTITLES_USER", ""),
            os.environ.get("OPENSUBTITLES_PASS", ""),
        )
        results = client.search(query=title, languages=[language])
        if not results or not results.data:
            return None
        subtitle_id = results.data[0].attributes.files[0].file_id
        download = client.download(subtitle_id)
        return download.content if download else None
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
        "Set OPENSUBTITLES_API_KEY or install faster-whisper."
    )
