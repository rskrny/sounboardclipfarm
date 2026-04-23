"""Preflight stage: validate request, classify content, and enforce source policy."""

from __future__ import annotations
from typing import Optional, List
from .models import MediaType

# Studios/Titles known to be strictly proprietary and unavailable via public discovery
_MAINSTREAM_RESTRICTED = [
    "nbc", "universal", "disney", "warner", "paramount", "mgm", "sony", "netflix", "hbo", "peacock",
    "the office", "friends", "seinfeld", "star wars", "marvel", "mcu", "batman", "harry potter",
    "game of thrones", "breaking bad", "better call soul", "stranger things"
]

class PreflightError(Exception):
    """Exception raised during preflight validation."""
    def __init__(self, message: str, actionable_hint: Optional[str] = None):
        super().__init__(message)
        self.actionable_hint = actionable_hint

def validate_request(
    title: str,
    media_type: MediaType = "movie",
    local_file: Optional[str] = None,
) -> None:
    """Check if the request is likely to succeed given current policy/sourcing.
    
    Raises PreflightError if the request is high-risk and missing a local file.
    """
    title_lower = title.lower()
    
    # 1. TV Series check: require season/episode or local file
    if media_type == "tv_series" and not local_file:
        # We don't have season/episode in the validation signature yet, 
        # but the point is to warn that discovery for TV is brittle.
        pass

    # 2. Mainstream Restricted check
    is_mainstream = any(keyword in title_lower for keyword in _MAINSTREAM_RESTRICTED)
    
    if is_mainstream and not local_file:
        raise PreflightError(
            f"'{title}' appears to be a mainstream commercial title.",
            actionable_hint=(
                "Due to licensing restrictions, automated discovery is very unlikely to succeed for this title. "
                "Please upload or provide a local media file to continue."
            )
        )

    # 3. Path space check (not strictly needed for Web UI but good for diagnostics)
    # (Removed as it's a shell issue, not a Python issue)

def get_diagnostics_report(tried_sources: List[str], error: Optional[Exception] = None) -> str:
    """Format a user-friendly diagnostic report for the UI."""
    report = "We attempted to find an authorized media source via:\n"
    report += "\n".join(f"- {s}" for s in tried_sources)
    
    if error:
        report += f"\n\nError detail: {str(error)}"
        
    report += "\n\nRecommendation: Upload a local file for commercial titles."
    return report
