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
        except Exception as e:
            # We could log this to a global diagnostic collector
            pass
        return None


class YouTubeSource:
    """Download audio from YouTube via yt-dlp.

    Pass 1 (youtube_cc):     CC-licensed content — cleanest rights posture.
    Pass 2 (youtube_promo):  Quote-targeted search — trailers/scene clips, no CC gate.
    Pass 3 (youtube_official):General fallback — broad search, last resort.

    Each pass yields a distinct ProviderID so the UI can show icons, copy,
    and disclosure appropriate to the source type.
    """
    name = "youtube_official"  # default; overridden per pass

    def find(self, title: str, quote: Optional[str] = None) -> Optional[MediaResult]:
        # Pass 1: youtube_cc — CC-licensed content
        if quote:
            result = self._try_query(
                title, f'ytsearch1:{title} "{quote}"',
                cc_only=True, provider_id="youtube_cc",
            )
            if result:
                return result
        result = self._try_query(
            title, f"ytsearch1:{title}",
            cc_only=True, provider_id="youtube_cc",
        )
        if result:
            return result

        # Pass 2: youtube_promo — quote-targeted scene/clip search
        if quote:
            for q in (f'ytsearch1:{title} "{quote}" scene', f'ytsearch1:{title} "{quote}"'):
                result = self._try_query(title, q, provider_id="youtube_promo")
                if result:
                    return result

        # Pass 3: youtube_official — broad fallback
        for q in (f"ytsearch1:{title} official clip", f"ytsearch1:{title} full movie"):
            result = self._try_query(title, q, provider_id="youtube_official")
            if result:
                return result

        return None

    def _try_query(
        self, title: str, query: str,
        cc_only: bool = False, provider_id: str = "youtube_official",
    ) -> Optional[MediaResult]:
        try:
            out_dir = tempfile.mkdtemp(prefix="clipfarm_yt_")
            out_template = os.path.join(out_dir, "%(id)s.%(ext)s")
            cmd = [
                "yt-dlp", "--no-playlist",
                "--format", "bestaudio/best",
                "--extract-audio", "--audio-format", "mp3",
                "--output", out_template,
                "--quiet",
            ]
            if cc_only:
                cmd += ["--match-filter", "license^=creativecommons"]
            cmd.append(query)

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if result.returncode != 0:
                stderr = result.stderr.strip() if result.stderr else "unknown error"
                # We could log this to a global diagnostic collector if available
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

            # Rights classification by search pass (provider_id is set by the caller)
            if cc_only:
                rights = RightsInfo(
                    policy="allowed_with_conditions",
                    source_detail="creative_commons_youtube",
                    provenance=f"yt-dlp CC-filtered search: {query}",
                    conditions="Attribution required per CC license terms.",
                )
            elif provider_id == "youtube_promo":
                rights = RightsInfo(
                    policy="review_needed",
                    source_detail="official_promo_or_clip",
                    provenance=f"yt-dlp targeted search: {query}",
                    conditions="Likely official promotional material. Review before commercial use.",
                )
            else:
                rights = RightsInfo(
                    policy="review_needed",
                    source_detail="no_license_verified",
                    provenance=f"yt-dlp search: {query}",
                    conditions="No license verified. Review rights before distribution.",
                )

            return MediaResult(
                file_path=local_path,
                title=title,
                source=provider_id,  # type: ignore[arg-type]
                duration_seconds=duration,
                rights=rights,
            )
        except Exception:
            return None


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
    attempts = []
    
    # 1. Local File
    if local_file:
        source = LocalFileSource(local_file)
        result = source.find(title)
        if result:
            return result
        attempts.append(f"local_file: Not found at {local_file}")
    else:
        attempts.append("local_file: No path provided")

    # Skip remote sources if requested
    if os.environ.get("CLIPFARM_SKIP_REMOTE") == "1":
        report = "\n".join(f"- {a}" for a in attempts)
        raise RuntimeError(
            f"Could not source media for '{title}'. Remote sources skipped per env var.\n"
            f"Attempts:\n{report}"
        )

    # 2. Internet Archive
    source_ia = InternetArchiveSource()
...


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
