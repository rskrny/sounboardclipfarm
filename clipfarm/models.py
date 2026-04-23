"""Shared data contracts between pipeline stages."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional


RightsPolicy = Literal["allowed", "allowed_with_conditions", "review_needed", "rejected"]


@dataclass
class RightsInfo:
    """Rights provenance attached to a resolved media source.

    policy values:
      allowed               — public domain, CC0, CC-BY; no material restrictions
      allowed_with_conditions — CC-BY-SA / CC-BY-NC; attribution or non-commercial req
      review_needed         — no explicit license detected; may be fair use; human review recommended
      rejected              — active rights enforcement evidence (Content ID, DMCA, etc.)

    Carry this through ClipResult so the UI/API never overstates what a source is allowed for.
    """
    policy: RightsPolicy
    source_detail: str    # e.g. "CC-BY 2.0", "public_domain", "no_license_detected"
    provenance: str       # e.g. "yt-dlp metadata: license=creativecommons.org/licenses/by/2.0/"
    conditions: str = ""  # human-readable conditions that apply, if any


@dataclass
class MediaResult:
    """Output from a MediaSource — a resolved local audio/video path."""
    file_path: str
    title: str
    source: Literal["local_file", "internet_archive", "youtube_official", "youtube_promo", "youtube_cc"]
    duration_seconds: float
    rights: Optional[RightsInfo] = None


@dataclass
class QuoteMatch:
    """Output from the quote matcher — a located transcript line with timestamps."""
    quote_text: str
    matched_text: str
    match_confidence: float          # 0.0–1.0 from rapidfuzz
    start_time: float                # seconds
    end_time: float                  # seconds
    subtitle_source: Literal["opensubtitles", "whisper", "local_srt", "none"]


@dataclass
class ClipRequest:
    """Handoff payload from matching → extraction."""
    media_path: str
    start_time: float
    end_time: float
    quote_text: str
    match_confidence: float
    subtitle_source: Literal["opensubtitles", "whisper", "local_srt", "none"]
    padding_before_ms: int = 200
    padding_after_ms: int = 200
    sample_rate: int = 44100
    channels: int = 1
    bit_depth: int = 16
    rights: Optional[RightsInfo] = None   # carried from MediaResult
    provider: str = "unknown"             # MediaResult.source identity (not a path)


@dataclass
class ClipResult:
    """Output from extraction — the final wav file with metadata."""
    output_path: str
    duration_seconds: float
    sample_rate: int
    channels: int
    bit_depth: int
    source_media: str                     # temp/local file path — internal detail
    provider: str                         # source identity: local_file | internet_archive | youtube
    quote_text: str
    match_confidence: float
    rights: Optional[RightsInfo] = None  # surface to UI/API — never suppress
