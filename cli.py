"""soundboardclipfarm CLI — extract a movie quote as a WAV clip."""

from __future__ import annotations
import argparse
import sys
from clipfarm.pipeline import run


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="clipfarm",
        description="Extract a movie/TV quote as a WAV audio clip.",
    )
    parser.add_argument("--movie", required=True, help="Movie or show title")
    parser.add_argument("--quote", required=True, help="Line or phrase to find")
    parser.add_argument("--output", required=True, help="Output .wav file path")
    parser.add_argument("--file", default=None, help="Path to local media file (optional)")
    parser.add_argument("--srt", default=None, help="Path to local .srt file (optional)")
    parser.add_argument("--sample-rate", type=int, default=44100, help="Output sample rate (default: 44100)")
    parser.add_argument("--channels", type=int, default=1, choices=[1, 2], help="1=mono, 2=stereo (default: 1)")
    parser.add_argument("--pad-before", type=int, default=200, help="Padding before clip in ms (default: 200)")
    parser.add_argument("--pad-after", type=int, default=200, help="Padding after clip in ms (default: 200)")
    parser.add_argument("--language", default="en", help="Subtitle language code (default: en)")

    args = parser.parse_args()

    try:
        result = run(
            title=args.movie,
            quote=args.quote,
            output_path=args.output,
            local_file=args.file,
            local_srt=args.srt,
            sample_rate=args.sample_rate,
            channels=args.channels,
            padding_before_ms=args.pad_before,
            padding_after_ms=args.pad_after,
            language=args.language,
        )
        print(f"Clip saved: {result.output_path}")
        print(f"Duration:   {result.duration_seconds:.2f}s")
        print(f"Format:     {result.sample_rate}Hz / {result.bit_depth}-bit / {'mono' if result.channels == 1 else 'stereo'}")
        print(f"Confidence: {result.match_confidence:.0%}")
        print(f"Source:     {result.source_media} (subtitles: {result.subtitle_source})")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
