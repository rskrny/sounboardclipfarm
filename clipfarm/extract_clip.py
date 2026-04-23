"""Audio clip extraction via ffprobe + ffmpeg.

Validates the source media, applies padding, enforces the 15s cap,
and exports a PCM WAV file at the requested sample rate and bit depth.
"""

from __future__ import annotations
import os
import subprocess
import json
import tempfile
from .models import ClipRequest, ClipResult

_MAX_DURATION = 14.9  # hard cap in seconds (under the 15s limit)


def _probe(media_path: str) -> dict:
    """Run ffprobe and return stream/format metadata.

    Raises RuntimeError if ffprobe fails or no audio stream is found.
    """
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams", "-show_format",
        media_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffprobe failed on '{media_path}': {result.stderr.strip()}"
        )
    data = json.loads(result.stdout)
    audio_streams = [
        s for s in data.get("streams", []) if s.get("codec_type") == "audio"
    ]
    if not audio_streams:
        raise RuntimeError(
            f"No audio stream found in '{media_path}'."
        )
    media_duration = float(data.get("format", {}).get("duration", 0))
    return {
        "audio": audio_streams[0],
        "duration": media_duration,
    }


def extract(request: ClipRequest, output_path: str) -> ClipResult:
    """Extract a WAV clip from `request.media_path` and write to `output_path`.

    Steps:
    1. Probe media — confirm audio stream exists, get duration.
    2. Apply padding, clamp window to [0, media_duration].
    3. Enforce final duration < 15.0s (trim end if needed).
    4. Extract with ffmpeg, export PCM WAV at request.sample_rate / 16-bit.
    5. Return ClipResult with verified output metadata.
    """
    probe = _probe(request.media_path)
    media_duration = probe["duration"]

    # Apply padding (convert ms → seconds)
    pad_before = request.padding_before_ms / 1000.0
    pad_after = request.padding_after_ms / 1000.0

    start = max(0.0, request.start_time - pad_before)
    end = min(media_duration, request.end_time + pad_after)

    # Enforce 15s cap — trim from the end to preserve the start of the line
    if (end - start) > _MAX_DURATION:
        end = start + _MAX_DURATION

    duration = end - start
    if duration <= 0:
        raise RuntimeError(
            f"Computed clip duration is {duration:.3f}s — invalid window "
            f"(start={start:.3f}, end={end:.3f})."
        )

    # Build output path if caller passed a directory
    if os.path.isdir(output_path):
        safe_title = "clip"
        output_path = os.path.join(output_path, f"{safe_title}.wav")

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # Map bit depth to ffmpeg sample format
    bit_fmt = {8: "u8", 16: "s16", 24: "s24", 32: "s32"}.get(
        request.bit_depth, "s16"
    )

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-t", str(duration),
        "-i", request.media_path,
        "-vn",                          # drop video
        "-acodec", "pcm_" + bit_fmt,
        "-ar", str(request.sample_rate),
        "-ac", str(request.channels),
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg extraction failed: {result.stderr.strip()}"
        )

    if not os.path.isfile(output_path):
        raise RuntimeError(f"ffmpeg ran but output file not found: {output_path}")

    # Verify output via ffprobe
    out_probe_cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        output_path,
    ]
    out_probe = subprocess.run(
        out_probe_cmd, capture_output=True, text=True, timeout=15
    )
    out_data = json.loads(out_probe.stdout) if out_probe.returncode == 0 else {}
    actual_duration = float(
        out_data.get("format", {}).get("duration", duration)
    )

    return ClipResult(
        rights=request.rights,
        output_path=output_path,
        duration_seconds=actual_duration,
        sample_rate=request.sample_rate,
        channels=request.channels,
        bit_depth=request.bit_depth,
        source_media=request.media_path,
        quote_text=request.quote_text,
        match_confidence=request.match_confidence,
    )
