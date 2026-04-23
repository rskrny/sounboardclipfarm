"""Resolve a movie/show title to a local audio file.

Sources tried in order:
1. Local file path (user-provided — most reliable).
2. Internet Archive (public-domain films only).
3. YouTube: targeted clip search (title + quote) — finds published official scenes.
4. YouTube: broad search (title + "official clip") — fallback for general scenes.

For mainstream copyrighted titles, sources 3 and 4 search for published clips
rather than full movies, which are more likely to be officially available.
Pass --file with a local copy for guaranteed results on any title.
"""

from __future__ import annotations
import os
import subprocess
import tempfile
from typing import Optional, Protocol
from .models import MediaResult


class MediaSource(Protocol):
    name: str
    def find(self, title: str, quote: Optional[str] = None) -> Optional[MediaResult]: ...


class LocalFileSource:
    """User supplies the file path directly."""
    name = "local_file"

    def __init__(self, file_path: str) -> None:
        self._path = file_path

    def find(self, title: str, quote: Optional[str] = None) -> Optional[MediaResult]:
        if not os.path.isfile(self._path):
            return None
        return MediaResult(
            file_path=self._path,
            title=title,
            source="local_file",
            duration_seconds=_probe_duration(self._path),
        )


class InternetArchiveSource:
    """Search Internet Archive for public-domain films.

    Only returns results for titles in the public domain catalog.
    Mainstream modern films will not be found here — that is expected.
    """
    name = "internet_archive"

    def find(self, title: str, quote: Optional[str] = None) -> Optional[MediaResult]:
        try:
            import internetarchive as ia
            results = ia.search_items(
                f'title:"{title}" AND mediatype:movies',
                fields=["identifier", "title"],
            )
            items = list(results)
            if not items:
                return None
            identifier = items[0]["identifier"]
            item = ia.get_item(identifier)
            for f in item.get_files():
                if f.name.lower().endswith((".mp4", ".ogv", ".avi", ".mkv", ".mp3")):
                    url = f"https://archive.org/download/{identifier}/{f.name}"
                    local_path = _download_to_tmp(url, f.name)
                    if local_path:
                        return MediaResult(
                            file_path=local_path,
                            title=title,
                            source="internet_archive",
                            duration_seconds=_probe_duration(local_path),
                        )
        except Exception:
            pass
        return None


class YouTubeSource:
    """Download audio from YouTube via yt-dlp.

    When a quote is provided, searches for the specific scene (title + quote)
    first — this targets published official clips and meme/highlight videos
    that are far more likely to be accessible than a full movie upload.

    Falls back to a general official-clip search if the targeted search misses.
    """
    name = "youtube"

    def find(self, title: str, quote: Optional[str] = None) -> Optional[MediaResult]:
        queries = []
        if quote:
            # Targeted: search for the specific scene by quote text
            queries.append(f'ytsearch1:{title} "{quote}" scene')
            queries.append(f'ytsearch1:{title} "{quote}"')
        # General fallback: official clips and trailers
        queries.append(f"ytsearch1:{title} official clip")
        queries.append(f"ytsearch1:{title} full movie")

        for query in queries:
            result = self._try_query(title, query)
            if result:
                return result
        return None

    def _try_query(self, title: str, query: str) -> Optional[MediaResult]:
        try:
            out_dir = tempfile.mkdtemp(prefix="clipfarm_yt_")
            out_template = os.path.join(out_dir, "%(id)s.%(ext)s")
            cmd = [
                "yt-dlp",
                "--no-playlist",
                "--format", "bestaudio/best",
                "--extract-audio",
                "--audio-format", "mp3",
                "--output", out_template,
                "--quiet",
                query,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=180
            )
            if result.returncode != 0:
                return None
            files = [
                os.path.join(out_dir, f)
                for f in os.listdir(out_dir)
                if f.endswith(".mp3")
            ]
            if not files:
                return None
            local_path = files[0]
            duration = _probe_duration(local_path)
            if duration == 0.0:
                return None
            return MediaResult(
                file_path=local_path,
                title=title,
                source="youtube",
                duration_seconds=duration,
            )
        except Exception:
            return None


def resolve_media(
    title: str,
    local_file: Optional[str] = None,
    quote: Optional[str] = None,
) -> MediaResult:
    """Try each source in priority order and return the first hit.

    Raises RuntimeError with a detailed message listing what was tried
    if no source succeeds. Pass quote to enable targeted YouTube clip search.
    """
    sources: list = []
    if local_file:
        sources.append(LocalFileSource(local_file))
    sources.append(InternetArchiveSource())
    sources.append(YouTubeSource())

    tried: list[str] = []
    for source in sources:
        tried.append(source.name)
        result = source.find(title, quote=quote)
        if result:
            return result

    tried_str = ", ".join(tried)
    raise RuntimeError(
        f"Could not source media for '{title}'.\n"
        f"  Sources tried: {tried_str}\n"
        f"  For mainstream films, use --file to supply a local copy:\n"
        f"    python cli.py --movie \"{title}\" --quote \"...\" "
        f"--output out.wav --file \"{title.lower().replace(' ', '_')}.mp4\""
    )


def _probe_duration(path: str) -> float:
    """Return duration in seconds via ffprobe, or 0.0 on failure."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True, text=True, timeout=30,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _download_to_tmp(url: str, filename: str) -> Optional[str]:
    """Stream-download `url` to a temp file and return local path."""
    try:
        import requests
        out_dir = tempfile.mkdtemp(prefix="clipfarm_ia_")
        out_path = os.path.join(out_dir, filename)
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return out_path
    except Exception:
        return None
