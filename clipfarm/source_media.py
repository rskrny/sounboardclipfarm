"""Resolve a movie/show title to a local audio file.

Sources tried in order:
1. Local file path (user-provided — most reliable).
2. Internet Archive (public-domain catalog).
3. YouTube CC-licensed content (yt-dlp --match-filter license^=creativecommons).
4. YouTube targeted clip search (title + quote), no license filter.
5. YouTube general fallback (official clip, then full movie), no license filter.

Every result carries a RightsInfo block with an explicit policy state:
  allowed / allowed_with_conditions / review_needed / rejected

Pass --file with a local copy for guaranteed results on any mainstream title.
"""

from __future__ import annotations
import os
import subprocess
import tempfile
from typing import Optional, Protocol
from .models import MediaResult, RightsInfo


class MediaSource(Protocol):
    name: str
    def find(self, title: str, quote: Optional[str] = None) -> Optional[MediaResult]: ...


class LocalFileSource:
    """User supplies the file path directly.

    Policy: allowed_with_conditions — the user is responsible for ensuring they
    have the right to use the file. We cannot verify; we flag it for transparency.
    """
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
            rights=RightsInfo(
                policy="allowed_with_conditions",
                source_detail="user_provided_file",
                provenance=f"local path: {self._path}",
                conditions="User is responsible for verifying they have rights to this file.",
            ),
        )


class InternetArchiveSource:
    """Search Internet Archive for public-domain films.

    Policy: allowed — Internet Archive's public domain catalog is definitively
    out of copyright. Only returns titles explicitly catalogued as public domain.
    """
    name = "internet_archive"

    def find(self, title: str, quote: Optional[str] = None) -> Optional[MediaResult]:
        try:
            import internetarchive as ia
            results = ia.search_items(
                f'title:"{title}" AND mediatype:movies AND subject:"public domain"',
                fields=["identifier", "title", "licenseurl"],
            )
            items = list(results)
            if not items:
                return None
            item_meta = items[0]
            identifier = item_meta["identifier"]
            license_url = item_meta.get("licenseurl", "public domain per archive.org catalog")
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
                            rights=RightsInfo(
                                policy="allowed",
                                source_detail="public_domain",
                                provenance=f"archive.org/{identifier} — {license_url}",
                            ),
                        )
        except Exception:
            pass
        return None


class YouTubeSource:
    """Download audio from YouTube via yt-dlp.

    Pass 1: CC-licensed content only (cleanest rights posture).
    Pass 2: Targeted clip search by quote (published scenes, no license gate).
    Pass 3: General fallback (official clip, full movie).

    Policy is determined by what yt-dlp metadata returns for the found video.
    CC videos → allowed or allowed_with_conditions.
    No-license videos → review_needed (never silently promoted to allowed).
    """
    name = "youtube"

    def find(self, title: str, quote: Optional[str] = None) -> Optional[MediaResult]:
        # Pass 1: CC-licensed content — cleanest rights posture
        if quote:
            result = self._try_query(title, f'ytsearch1:{title} "{quote}"', cc_only=True)
            if result:
                return result
        result = self._try_query(title, f"ytsearch1:{title}", cc_only=True)
        if result:
            return result

        # Pass 2: targeted clip search, all results
        if quote:
            for q in (f'ytsearch1:{title} "{quote}" scene', f'ytsearch1:{title} "{quote}"'):
                result = self._try_query(title, q)
                if result:
                    return result

        # Pass 3: general fallback
        for q in (f"ytsearch1:{title} official clip", f"ytsearch1:{title} full movie"):
            result = self._try_query(title, q)
            if result:
                return result

        return None

    def _try_query(self, title: str, query: str, cc_only: bool = False) -> Optional[MediaResult]:
        try:
            out_dir = tempfile.mkdtemp(prefix="clipfarm_yt_")
            out_template = os.path.join(out_dir, "%(id)s.%(ext)s")
            # Also dump metadata so we can read the license field
            meta_file = os.path.join(out_dir, "meta.json")
            cmd = [
                "yt-dlp",
                "--no-playlist",
                "--format", "bestaudio/best",
                "--extract-audio",
                "--audio-format", "mp3",
                "--output", out_template,
                "--quiet",
                "--dump-single-json",
            ]
            if cc_only:
                cmd += ["--match-filter", "license^=creativecommons"]
            cmd.append(query)

            # First: dump metadata only to check rights before downloading
            meta_cmd = [
                "yt-dlp", "--no-playlist", "--quiet",
                "--dump-single-json",
            ]
            if cc_only:
                meta_cmd += ["--match-filter", "license^=creativecommons"]
            meta_cmd.append(query)

            import json
            meta_result = subprocess.run(
                meta_cmd, capture_output=True, text=True, timeout=30
            )
            if meta_result.returncode != 0 or not meta_result.stdout.strip():
                return None

            try:
                meta = json.loads(meta_result.stdout)
            except json.JSONDecodeError:
                return None

            video_id = meta.get("id", "unknown")
            video_title = meta.get("title", title)
            license_str = meta.get("license") or ""
            uploader = meta.get("uploader", "unknown")
            webpage_url = meta.get("webpage_url", f"https://youtube.com/watch?v={video_id}")

            rights = _classify_yt_rights(license_str, uploader, webpage_url)

            # Now download audio
            dl_cmd = [
                "yt-dlp", "--no-playlist",
                "--format", "bestaudio/best",
                "--extract-audio", "--audio-format", "mp3",
                "--output", out_template,
                "--quiet",
            ]
            if cc_only:
                dl_cmd += ["--match-filter", "license^=creativecommons"]
            dl_cmd.append(query)

            dl_result = subprocess.run(dl_cmd, capture_output=True, text=True, timeout=180)
            if dl_result.returncode != 0:
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
                title=video_title,
                source="youtube",
                duration_seconds=duration,
                rights=rights,
            )
        except Exception:
            return None


def _classify_yt_rights(license_str: str, uploader: str, url: str) -> RightsInfo:
    """Map yt-dlp license metadata to an explicit RightsInfo policy."""
    ls = license_str.lower()
    provenance = f"yt-dlp metadata: uploader={uploader!r}, url={url}, license={license_str!r}"

    if "creativecommons.org/licenses/by/4" in ls or "creativecommons.org/licenses/by/2" in ls:
        return RightsInfo(
            policy="allowed",
            source_detail=f"CC-BY ({license_str})",
            provenance=provenance,
            conditions="Attribution required: credit the uploader.",
        )
    if "creativecommons.org/publicdomain/zero" in ls or "cc0" in ls:
        return RightsInfo(
            policy="allowed",
            source_detail="CC0 / public domain dedication",
            provenance=provenance,
        )
    if "creativecommons" in ls and "nc" in ls:
        return RightsInfo(
            policy="allowed_with_conditions",
            source_detail=f"CC Non-Commercial ({license_str})",
            provenance=provenance,
            conditions="Non-commercial use only. Attribution required.",
        )
    if "creativecommons" in ls:
        return RightsInfo(
            policy="allowed_with_conditions",
            source_detail=f"Creative Commons ({license_str})",
            provenance=provenance,
            conditions="Review specific CC license terms before use.",
        )
    # No explicit license detected — must not be promoted to allowed
    return RightsInfo(
        policy="review_needed",
        source_detail="no_license_detected",
        provenance=provenance,
        conditions=(
            "No explicit license found. Verify rights before use. "
            "May qualify as fair use for non-commercial/transformative purposes — "
            "human review required."
        ),
    )


def resolve_media(
    title: str,
    local_file: Optional[str] = None,
    quote: Optional[str] = None,
) -> MediaResult:
    """Try each source in priority order and return the first hit.

    The returned MediaResult always carries a RightsInfo block. Callers must
    surface this to the user — never suppress the policy or conditions fields.

    Raises RuntimeError with diagnostics listing each source tried if all fail.
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
