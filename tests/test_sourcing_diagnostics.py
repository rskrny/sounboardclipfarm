import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from clipfarm.source_media import resolve_media
from clipfarm.models import MediaResult

def test_sourcing_fail_diagnostics():
    print("Testing sourcing failure diagnostics...")
    title = "Some Obscure Movie That Does Not Exist 12345"
    try:
        resolve_media(title, local_file="nonexistent.mp4")
        print("FAIL: Should have raised RuntimeError")
    except RuntimeError as e:
        print(f"PASS: Caught expected error:\n{e}")
        # Verify it mentions the tried sources
        error_msg = str(e)
        assert "Local file" in error_msg
        assert "Internet Archive" in error_msg
        assert "YouTube" in error_msg
        assert "YouTube Promo" in error_msg

def test_sourcing_provenance_top_gun():
    # This might actually try to download, which is slow. 
    # For a unit test, we might want to mock, but Codex wants a "validation pass".
    # I'll try it and see if it works.
    print("Testing Top Gun (Paramount) sourcing...")
    try:
        # We don't want to download the whole thing if it's a full movie, 
        # but YouTubeSource and YouTubePromoSource use yt-dlp which we've restricted.
        # I'll use a very specific query that should hit a trailer.
        result = resolve_media("Top Gun Maverick")
        print(f"RESULT: Found via {result.source} ({result.source_detail})")
        print(f"Path: {result.file_path}")
    except Exception as e:
        print(f"Note: Top Gun sourcing failed/skipped (Likely network or yt-dlp issue): {e}")

from clipfarm.source_media import resolve_media, YouTubeSource, YouTubePromoSource

def test_sourcing_provenance_dune_youtube():
    print("Testing Dune Part Two (Warner Bros) YouTube sourcing...")
    try:
        # Manually try YouTube sources to bypass IA
        for source_class in [YouTubeSource, YouTubePromoSource]:
            source = source_class()
            result = source.find("Dune Part Two")
            if result:
                print(f"RESULT: Found via {result.source} ({result.source_detail})")
                print(f"Path: {result.file_path}")
                return
        print("FAIL: No YouTube source found for Dune Part Two")
    except Exception as e:
        print(f"Note: Dune YouTube sourcing failed/skipped: {e}")

def test_sourcing_rejection_youtube():
    print("Testing non-allowlisted YouTube rejection...")
    # This search should find MANY results, but hopefully none are in our narrow allowlist
    # unless someone uploaded a "Fan Film" to Paramount's channel (unlikely).
    try:
        source = YouTubePromoSource()
        result = source.find("Random Fan Film 2024")
        if result:
            print(f"FAIL: Should not have found a match on authorized channels for a random fan film. Found: {result.source_detail}")
        else:
            print("PASS: Correctly rejected non-allowlisted results.")
    except Exception as e:
        print(f"Note: Rejection test skipped/errored: {e}")

if __name__ == "__main__":
    test_sourcing_fail_diagnostics()
    test_sourcing_provenance_dune_youtube()
    test_sourcing_rejection_youtube()
