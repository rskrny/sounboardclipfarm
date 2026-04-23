import pysrt
from typing import List, Dict, Optional
from pathlib import Path

class SubtitleBlock:
    def __init__(self, start_ms: int, end_ms: int, text: str):
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.text = text

class SubtitleProcessor:
    """
    Handles subtitle parsing and manipulation.
    """
    def __init__(self, subtitle_path: str):
        self.subtitle_path = subtitle_path
        try:
            self.subs = pysrt.open(subtitle_path)
        except Exception as e:
            # Fallback for encoding issues
            self.subs = pysrt.open(subtitle_path, encoding='iso-8859-1')

    def get_all_blocks(self) -> List[SubtitleBlock]:
        """
        Convert pysrt items to simple SubtitleBlock objects.
        """
        blocks = []
        for sub in self.subs:
            blocks.append(SubtitleBlock(
                start_ms=sub.start.ordinal,
                end_ms=sub.end.ordinal,
                text=sub.text
            ))
        return blocks

    def stitch_blocks(self, start_index: int, end_index: int) -> SubtitleBlock:
        """
        Combine multiple subtitle blocks into one.
        """
        if start_index < 0 or end_index >= len(self.subs) or start_index > end_index:
            raise ValueError("Invalid block range")
            
        selected = self.subs[start_index : end_index + 1]
        
        return SubtitleBlock(
            start_ms=selected[0].start.ordinal,
            end_ms=selected[-1].end.ordinal,
            text=" ".join([s.text for s in selected])
        )

    def find_block_at_timestamp(self, timestamp_ms: int) -> Optional[int]:
        """
        Find the index of the subtitle block at a specific timestamp.
        """
        for i, sub in enumerate(self.subs):
            if sub.start.ordinal <= timestamp_ms <= sub.end.ordinal:
                return i
        return None
