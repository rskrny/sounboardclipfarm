"""Orchestrates all pipeline stages end-to-end."""

from __future__ import annotations
from typing import Optional
from .models import ClipRequest, ClipResult
from .fetch_transcript import get_transcript
from .match_quote import find_quote
from .source_media import resolve_media


def run(
    title: str,
    quote: str,
    output_path: str,
    local_file: Optional[str] = None,
    local_srt: Optional[str] = None,
    sample_rate: int = 44100,
    channels: int = 1,
    padding_before_ms: int = 200,
    padding_after_ms: int = 200,
    language: str = "en",
) -> ClipResult:
    """Full pipeline: title + quote → .wav clip.

    Args:
        title: Movie or show name.
        quote: Line or phrase to locate.
        output_path: Destination .wav file path.
        local_file: Optional path to a media file the user already has.
        local_srt: Optional path to a local .srt file.
        sample_rate: Output sample rate in Hz.
        channels: 1 = mono, 2 = stereo.
        padding_before_ms: Milliseconds of audio before the matched line.
        padding_after_ms: Milliseconds of audio after the matched line.
        language: Subtitle language code for OpenSubtitles lookup.

    Returns:
        ClipResult with output path and metadata.
    """
    # Stage 1 — source media (pass quote for targeted YouTube clip search)
    media = resolve_media(title, local_file=local_file, quote=quote)

    # Stage 2 — fetch transcript
    subtitles, subtitle_source = get_transcript(
        title,
        media_path=media.file_path,
        local_srt=local_srt,
        language=language,
    )

    # Stage 3 — match quote
    match = find_quote(quote, subtitles, subtitle_source)

    # Stage 4 — build extraction request and hand off
    request = ClipRequest(
        media_path=media.file_path,
        start_time=match.start_time,
        end_time=match.end_time,
        quote_text=match.quote_text,
        match_confidence=match.match_confidence,
        subtitle_source=match.subtitle_source,
        padding_before_ms=padding_before_ms,
        padding_after_ms=padding_after_ms,
        sample_rate=sample_rate,
        channels=channels,
        bit_depth=16,
    )

    # Stage 5 — extract clip (owned by codex / extract_clip.py)
    from .extract_clip import extract  # imported here; codex implements this
    return extract(request, output_path)
