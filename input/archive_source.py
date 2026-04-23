import internetarchive as ia
from pathlib import Path
from typing import Optional, List
import logging

log = logging.getLogger(__name__)

class ArchiveSource:
    """
    Sourcing module for Internet Archive (archive.org).
    Searches for movies and downloads the most relevant media and subtitle files.
    """
    def __init__(self, download_dir: str = "media"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def search_and_fetch(self, movie_name: str) -> Optional[dict]:
        """
        Search for a movie and download its media/subtitles if found.
        """
        query = f"title:({movie_name}) AND mediatype:(movies)"
        search = ia.search_items(query, sort_by="downloads desc")
        
        for result in search:
            item_id = result['identifier']
            item = ia.get_item(item_id)
            
            # Look for video files and subtitles
            video_file = None
            subtitle_file = None
            
            for file in item.files:
                name = file['name']
                format = file.get('format', '')
                
                if not video_file and any(ext in name.lower() for ext in ['.mp4', '.mkv', '.avi']):
                    video_file = name
                if not subtitle_file and any(ext in name.lower() for ext in ['.srt', '.vtt']):
                    subtitle_file = name
                    
            if video_file:
                log.info(f"Found movie on Internet Archive: {item_id}")
                
                # Download video and subtitle
                ia.download(item_id, files=[video_file], destdir=str(self.download_dir), ignore_existing=True)
                if subtitle_file:
                    ia.download(item_id, files=[subtitle_file], destdir=str(self.download_dir), ignore_existing=True)
                
                return {
                    "media_path": self.download_dir / item_id / video_file,
                    "subtitle_path": self.download_dir / item_id / subtitle_file if subtitle_file else None,
                    "source": "archive.org",
                    "identifier": item_id
                }
        
        return None
