import click
import sys
from pathlib import Path
from input.media_resolver import MediaResolver
from matching.quote_matcher import QuoteMatcher
from matching.subtitle_processor import SubtitleProcessor

@click.command()
@click.option('--movie', required=True, help='Name of the movie or TV show.')
@click.option('--phrase', required=True, help='The line or phrase to extract.')
@click.option('--sample-rate', default=44100, type=int, help='Output sample rate (default: 44100).')
@click.option('--media-dir', default='media', help='Directory containing media files.')
@click.option('--output-dir', default='clips', help='Directory to save extracted clips.')
@click.option('--padding', default=500, type=int, help='Padding in milliseconds before and after the clip (default: 500).')
def main(movie, phrase, sample_rate, media_dir, output_dir, padding):
    """
    Soundboard Clip Farm: Extract movie audio clips based on a phrase.
    """
    click.echo(f"Searching for '{phrase}' in '{movie}'...")

    # 1. Resolve Media
    resolver = MediaResolver(media_dir=media_dir)
    media_result = resolver.resolve(movie)

    if not media_result:
        click.echo(f"Error: Could not find media for '{movie}' in '{media_dir}'", err=True)
        sys.exit(1)

    click.echo(f"Found media: {media_result.media_path}")
    
    if not media_result.subtitle_path:
        click.echo("Error: No subtitle file found. AI-based matching (Whisper) is not yet implemented.", err=True)
        sys.exit(1)

    click.echo(f"Using subtitles: {media_result.subtitle_path}")

    # 2. Match Quote
    matcher = QuoteMatcher(str(media_result.subtitle_path))
    match = matcher.find_multi_block_match(phrase)

    if not match:
        click.echo(f"Error: Could not find phrase '{phrase}' in subtitles.", err=True)
        sys.exit(1)

    click.echo(f"Match found (confidence: {match.confidence:.2f}%):")
    click.echo(f"Text: \"{match.text}\"")
    click.echo(f"Timing: {match.start_time_ms}ms to {match.end_time_ms}ms")

    # 3. Prepare Extraction Request
    request = ExtractionRequest(
        media_path=media_result.media_path,
        start_time=match.start_time_ms / 1000.0,
        end_time=match.end_time_ms / 1000.0,
        quote_text=match.text,
        match_confidence=match.confidence,
        subtitle_source="local_srt", # Assuming local for now
        sample_rate=sample_rate,
        padding_before_ms=padding,
        padding_after_ms=padding
    )

    # 4. Extract (Mocked for now)
    output_path = Path(output_dir) / f"{movie.replace(' ', '_')}_clip.wav"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    click.echo("\n--- Extraction Handoff (Mocked with ExtractionRequest) ---")
    click.echo(f"Media Path: {request.media_path}")
    click.echo(f"Requested Window: {request.start_time:.3f}s to {request.end_time:.3f}s")
    click.echo(f"Padding: {request.padding_before_ms}ms / {request.padding_after_ms}ms")
    click.echo(f"Sample Rate: {request.sample_rate}")
    click.echo(f"Output Path: {output_path}")
    click.echo("----------------------------------------------------------\n")

    click.echo("Standing by for Codex's extraction module implementation.")

if __name__ == '__main__':
    from extraction import ExtractionRequest, ExtractionResult
    main()
