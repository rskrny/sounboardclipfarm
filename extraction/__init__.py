from pathlib import Path
from typing import Optional, Dict, Literal

class ExtractionRequest:
    def __init__(
        self,
        media_path: Path,
        start_time: float,
        end_time: float,
        quote_text: str,
        match_confidence: float,
        subtitle_source: Literal["opensubtitles", "whisper", "local_srt", "none"],
        sample_rate: int = 44100,
        channels: int = 2,
        bit_depth: int = 16,
        padding_before_ms: int = 500,
        padding_after_ms: int = 500
    ):
        self.media_path = media_path
        self.start_time = start_time
        self.end_time = end_time
        self.quote_text = quote_text
        self.match_confidence = match_confidence
        self.subtitle_source = subtitle_source
        self.sample_rate = sample_rate
        self.channels = channels
        self.bit_depth = bit_depth
        self.padding_before_ms = padding_before_ms
        self.padding_after_ms = padding_after_ms

class ExtractionResult:
    def __init__(
        self,
        output_path: Path,
        actual_start: float,
        actual_end: float,
        final_duration: float,
        metadata: Optional[Dict] = None,
        error: Optional[str] = None
    ):
        self.output_path = output_path
        self.actual_start = actual_start
        self.actual_end = actual_end
        self.final_duration = final_duration
        self.metadata = metadata or {}
        self.error = error

class ExtractionError(Exception):
    """Base class for extraction errors."""
    pass

class MediaNotFoundError(ExtractionError):
    pass

class NoAudioStreamError(ExtractionError):
    pass

class InvalidWindowError(ExtractionError):
    pass

class ExportFailedError(ExtractionError):
    pass
