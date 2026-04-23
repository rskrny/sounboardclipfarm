import re
from typing import List, Dict, Optional, Tuple
from rapidfuzz import fuzz, process
import pysrt

class MatchResult:
    def __init__(self, start_time_ms: int, end_time_ms: int, text: str, confidence: float):
        self.start_time_ms = start_time_ms
        self.end_time_ms = end_time_ms
        self.text = text
        self.confidence = confidence

class QuoteMatcher:
    """
    Matches a user-provided phrase against a subtitle file.
    """
    def __init__(self, subtitle_path: str):
        self.subtitle_path = subtitle_path
        self.subs = pysrt.open(subtitle_path)
        self.normalized_subs = self._normalize_subs()

    def _normalize_text(self, text: str) -> str:
        """
        Lowercase and strip punctuation.
        """
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        return text.strip()

    def _normalize_subs(self) -> List[Dict]:
        """
        Pre-calculate normalized text for all subtitle blocks.
        """
        normalized = []
        for index, sub in enumerate(self.subs):
            normalized.append({
                "index": index,
                "text": self._normalize_text(sub.text),
                "original_text": sub.text,
                "start": sub.start.ordinal, # milliseconds
                "end": sub.end.ordinal      # milliseconds
            })
        return normalized

    def find_match(self, phrase: str, threshold: float = 80.0) -> Optional[MatchResult]:
        """
        Find the best matching subtitle block for the given phrase.
        Simple single-block match.
        """
        target = self._normalize_text(phrase)
        texts = [s["text"] for s in self.normalized_subs]
        
        # Use rapidfuzz to find the best match
        best_match = process.extractOne(target, texts, scorer=fuzz.token_set_ratio)
        
        if best_match and best_match[1] >= threshold:
            match_text, score, index = best_match
            sub_data = self.normalized_subs[index]
            return MatchResult(
                start_time_ms=sub_data["start"],
                end_time_ms=sub_data["end"],
                text=sub_data["original_text"],
                confidence=score
            )
            
        return None

    def find_multi_block_match(self, phrase: str, threshold: float = 80.0) -> Optional[MatchResult]:
        """
        Handle cases where a quote spans across multiple subtitle blocks.
        Stitches blocks together in sliding windows.
        """
        target = self._normalize_text(phrase)
        phrase_words = target.split()
        if not phrase_words:
            return None

        # Create windows of stitched subtitle text
        # We'll try windows of size 1 to 5 blocks
        best_overall = None
        
        for window_size in range(1, 6):
            for i in range(len(self.normalized_subs) - window_size + 1):
                window = self.normalized_subs[i:i+window_size]
                stitched_text = " ".join([s["text"] for s in window])
                
                score = fuzz.token_sort_ratio(target, stitched_text)
                
                if score >= threshold:
                    if best_overall is None or score > best_overall["score"] or (score == best_overall["score"] and window_size < best_overall["window_size"]):
                        best_overall = {
                            "score": score,
                            "window_size": window_size,
                            "start": window[0]["start"],
                            "end": window[-1]["end"],
                            "text": " ".join([s["original_text"] for s in window])
                        }
        
        if best_overall:
            return MatchResult(
                start_time_ms=best_overall["start"],
                end_time_ms=best_overall["end"],
                text=best_overall["text"],
                confidence=best_overall["score"]
            )
            
        return None
