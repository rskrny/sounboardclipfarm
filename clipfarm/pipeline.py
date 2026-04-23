"""Orchestrates all pipeline stages end-to-end."""

from __future__ import annotations
from typing import Callable, Optional
from .models import ClipRequest, ClipResult
from .fetch_transcript import get_transcript
from .match_quote import find_quote
from .source_media import resolve_media
from .preflight import check as preflight_check

ProgressCallback = Callable[[str, str], None]  # (stage, message)


def _probe_duration(path: str) -> float:
    import subprocess, json
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
            capture_output=True, text=True, timeout=15,
        )
        return float(json.loads(r.stdout).get("format", {}).get("duration", 0))
    except Exception:
        return 0.0


def run(
    title: str,        # empty string triggers quote-only identification mode
    quote: str,
    output_path: str,
    local_file: Optional[str] = None,
    local_srt: Optional[str] = None,
    sample_rate: int = 44100,
    channels: int = 1,
    padding_before_ms: int = 200,
    padding_after_ms: int = 200,
    language: str = "en",
    media_type: str = "movie",
    season: Optional[int] = None,
    episode: Optional[int] = None,
    on_progress: Optional[ProgressCallback] = None,
) -> ClipResult:
    """Full pipeline: title + quote → .wav clip.

    on_progress(stage, message) is called at the start of each stage so
    callers (e.g. the service layer) can surface live progress to the UI.
    """
    def _progress(stage: str, message: str) -> None:
        if on_progress:
            on_progress(stage, message)

    # Stage 0A — quote-only identification mode (title not provided)
    if not title.strip():
        _progress("identifying", f"No title given — searching for: '{quote}'…")
        from .quote_identify import identify, QuoteIdentification
        ident: QuoteIdentification = identify(quote, language=language)
        _progress("identifying", f"Found: '{ident.title}' (via {ident.provider}, {ident.confidence:.0%} confidence)")
        title = ident.title

        # If the identifier already fetched the clip (GetYarn), go straight to extraction
        if ident.media_path:
            from .extract_clip import extract
            from .models import RightsInfo
            request = ClipRequest(
                media_path=ident.media_path,
                start_time=0.0,
                end_time=_probe_duration(ident.media_path),
                quote_text=quote,
                match_confidence=ident.confidence,
                subtitle_source="none",
                padding_before_ms=0,
                padding_after_ms=0,
                sample_rate=sample_rate,
                channels=channels,
                bit_depth=16,
                rights=RightsInfo(
                    policy="review_needed",
                    source_detail="getyarn_clip",
                    provenance=f"getyarn.io title-free quote search: '{quote}'",
                    conditions="Clip from GetYarn.io. Personal/non-commercial soundboard use.",
                ),
                provider=ident.provider,
                media_type=media_type,
            )
            _progress("extraction", "Converting GetYarn clip to WAV…")
            result = extract(request, output_path)
            result.media_type = media_type
            _progress("extraction", f"Clip saved: {result.output_path} ({result.duration_seconds:.2f}s)")
            return result

    # Stage 0B — preflight (non-blocking warnings only; service layer handles blocking)
    _progress("preflight", f"Validating request for '{title}'…")
    pf = preflight_check(
        title=title, quote=quote, local_file=local_file,
        media_type=media_type, season=season, episode=episode,
    )
    if pf.blocking:
        err = RuntimeError(pf.user_message)
        err.actionable_hint = pf.user_message  # type: ignore[attr-defined]
        raise err
    if pf.decision != "ready":
        _progress("preflight", pf.user_message)

    # Stage 1 — source media
    _progress("sourcing", f"Searching for '{title}'…")
    media = resolve_media(title, local_file=local_file, quote=quote)
    _progress("sourcing", f"Found via {media.source}: {media.file_path}")

    # Stage 2 — fetch transcript
    _progress("transcript", f"Fetching transcript ({language})…")
    subtitles, subtitle_source = get_transcript(
        title,
        media_path=media.file_path,
        local_srt=local_srt,
        language=language,
    )
    _progress("transcript", f"Got {len(subtitles)} subtitle lines via {subtitle_source}")

    # Stage 3 — match quote
    _progress("matching", f"Matching quote: '{quote}'")
    match = find_quote(quote, subtitles, subtitle_source)
    _progress(
        "matching",
        f"Match at {match.start_time:.2f}s–{match.end_time:.2f}s "
        f"(confidence {match.match_confidence:.0%}): '{match.matched_text}'",
    )

    # Stage 4 — build extraction request
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
        rights=media.rights,
        provider=media.source,  # identity string, not a file path
        media_type=media_type,
        season=season,
        episode=episode,
    )

    # Stage 5 — extract clip
    _progress("extraction", f"Extracting {match.end_time - match.start_time:.2f}s clip…")
    from .extract_clip import extract
    result = extract(request, output_path)
    
    # Update result with TV hierarchy
    result.media_type = media_type
    result.season = season
    result.episode = episode
    
    _progress("extraction", f"Clip saved: {result.output_path} ({result.duration_seconds:.2f}s)")

    return result
