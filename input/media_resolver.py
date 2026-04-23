import os
from pathlib import Path
from typing import Optional, List, Dict

class MediaResult:
    def __init__(self, media_path: Path, subtitle_path: Optional[Path] = None, metadata: Optional[Dict] = None):
        self.media_path = media_path
        self.subtitle_path = subtitle_path
        self.metadata = metadata or {}

from input.archive_source import ArchiveSource

class MediaResolver:
    """
    Resolves a movie name to a media file and its associated subtitle file.
    Prioritizes local files, then falls back to Internet Archive.
    """
    def __init__(self, media_dir: str = "media", use_archive: bool = True):
        self.media_dir = Path(media_dir)
        self.use_archive = use_archive
        self.archive = ArchiveSource(download_dir=media_dir) if use_archive else None
        self.supported_media_exts = {".mp4", ".mkv", ".avi", ".mov", ".m4v"}
        self.supported_subtitle_exts = {".srt", ".vtt"}

    def resolve(self, movie_name: str) -> Optional[MediaResult]:
        """
        Search for a movie by name in the media directory, then Internet Archive.
        """
        # 1. Local Search
        if self.media_dir.exists():
            movie_name_clean = movie_name.lower().replace(" ", "_")
            for file in self.media_dir.iterdir():
                if file.suffix.lower() in self.supported_media_exts:
                    if movie_name_clean in file.name.lower().replace(" ", "_"):
                        subtitle_path = self._find_subtitle(file)
                        return MediaResult(media_path=file, subtitle_path=subtitle_path, metadata={"source": "local"})

        # 2. Archive.org Fallback
        if self.use_archive:
            result = self.archive.search_and_fetch(movie_name)
            if result:
                return MediaResult(
                    media_path=result["media_path"],
                    subtitle_path=result["subtitle_path"],
                    metadata={"source": "archive.org", "identifier": result["identifier"]}
                )
        
        return None

    def _find_subtitle(self, media_file: Path) -> Optional[Path]:
        """
        Look for a subtitle file with the same base name as the media file.
        """
        base_name = media_file.stem
        for ext in self.supported_subtitle_exts:
            subtitle_file = media_file.parent / f"{base_name}{ext}"
            if subtitle_file.exists():
                return subtitle_file
        
        # Also check for .en.srt etc.
        for file in media_file.parent.iterdir():
            if file.suffix.lower() in self.supported_subtitle_exts:
                if file.stem.startswith(base_name):
                    return file
                    
        return None
