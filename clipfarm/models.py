"""Shared data contracts between pipeline stages."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class MediaResult:
    """Output from a MediaSource — a resolved local audio/video path."""
    file_path: str
    title: str
    source: Literal["local_file", "internet_archive", "youtube"]
    duration_seconds: float


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


@dataclass
class ClipResult:
    """Output from extraction — the final wav file with metadata."""
    output_path: str
    duration_seconds: float
    sample_rate: int
    channels: int
    bit_depth: int
    source_media: str
    quote_text: str
    match_confidence: float
