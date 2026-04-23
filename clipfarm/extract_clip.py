"""Audio clip extraction — owned by codex.

Stub implementation. Replace with full ffprobe validation + ffmpeg extraction.
See ClipRequest/ClipResult contracts in models.py.
"""

from __future__ import annotations
from .models import ClipRequest, ClipResult


def extract(request: ClipRequest, output_path: str) -> ClipResult:
    """Extract a WAV clip from `request.media_path` and write to `output_path`.

    Implementation owned by codex. Contract:
    - Apply padding (clamp to media duration).
    - Enforce final duration < 15.0s.
    - Verify at least one audio stream via ffprobe before export.
    - Export PCM WAV, 16-bit, request.sample_rate, request.channels.
    - Return ClipResult with output metadata.
    """
    raise NotImplementedError("extract_clip.py implementation owned by codex.")
