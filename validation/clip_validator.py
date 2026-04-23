import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional

class ClipValidator:
    """
    Validates extracted audio clips using ffprobe.
    """
    def __init__(self, ffprobe_path: str = "ffprobe"):
        self.ffprobe_path = ffprobe_path

    def validate(self, clip_path: Path, expected_sample_rate: int = 44100) -> Dict[str, Any]:
        """
        Check if the clip meets the project requirements.
        Returns a dict with 'valid' (bool) and 'errors' (list of strings).
        """
        results = {
            "valid": True,
            "errors": [],
            "metadata": {}
        }

        if not clip_path.exists():
            results["valid"] = False
            results["errors"].append("File does not exist")
            return results

        try:
            metadata = self._get_metadata(clip_path)
            results["metadata"] = metadata
        except Exception as e:
            results["valid"] = False
            results["errors"].append(f"Failed to probe file: {str(e)}")
            return results

        # 1. Format check (must be wav)
        format_name = metadata.get("format", {}).get("format_name", "")
        if "wav" not in format_name.lower():
            results["valid"] = False
            results["errors"].append(f"Invalid format: {format_name} (expected wav)")

        # 2. Duration check (must be <= 15s)
        duration = float(metadata.get("format", {}).get("duration", 0))
        if duration > 15.1: # Allow a tiny bit of slack for rounding
            results["valid"] = False
            results["errors"].append(f"Duration too long: {duration:.2f}s (max 15s)")

        # 3. Stream checks
        streams = metadata.get("streams", [])
        if not streams:
            results["valid"] = False
            results["errors"].append("No audio streams found")
            return results

        audio_stream = streams[0]
        
        # Sample rate check
        sample_rate = int(audio_stream.get("sample_rate", 0))
        if sample_rate != expected_sample_rate:
            results["valid"] = False
            results["errors"].append(f"Invalid sample rate: {sample_rate} (expected {expected_sample_rate})")

        # Bit depth check (s16 for 16-bit)
        sample_fmt = audio_stream.get("sample_fmt", "")
        if sample_fmt != "s16":
            results["valid"] = False
            results["errors"].append(f"Invalid sample format: {sample_fmt} (expected s16)")

        return results

    def _get_metadata(self, clip_path: Path) -> Dict[str, Any]:
        """
        Run ffprobe to get JSON metadata.
        """
        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(clip_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
