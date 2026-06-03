"""
ClipGenius - Input Validators
==============================
Validates user inputs like YouTube URLs before processing.
"""

import re
from loguru import logger


# Regex patterns for YouTube URL formats
_YT_PATTERNS = [
    r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]{11}",
    r"(?:https?://)?youtu\.be/[\w-]{11}",
    r"(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]{11}",
    r"(?:https?://)?(?:www\.)?youtube\.com/embed/[\w-]{11}",
    r"(?:https?://)?(?:m\.)?youtube\.com/watch\?v=[\w-]{11}",
]

_COMBINED_PATTERN = re.compile("|".join(_YT_PATTERNS))


def is_valid_youtube_url(url: str) -> bool:
    """
    Check whether *url* looks like a valid YouTube video link.

    Supports:
        - youtube.com/watch?v=...
        - youtu.be/...
        - youtube.com/shorts/...
        - youtube.com/embed/...
        - m.youtube.com/watch?v=...

    Returns True if the URL matches, False otherwise.
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()
    match = _COMBINED_PATTERN.search(url)

    if match:
        logger.debug(f"URL validated successfully: {url}")
        return True

    logger.warning(f"Invalid YouTube URL: {url}")
    return False


def extract_video_id(url: str) -> str | None:
    """
    Extract the 11-character video ID from a YouTube URL.
    
    Returns the video ID string or None if extraction fails.
    """
    if not is_valid_youtube_url(url):
        return None

    url = url.strip()

    # Pattern: youtube.com/watch?v=VIDEO_ID
    match = re.search(r"[?&]v=([\w-]{11})", url)
    if match:
        return match.group(1)

    # Pattern: youtu.be/VIDEO_ID
    match = re.search(r"youtu\.be/([\w-]{11})", url)
    if match:
        return match.group(1)

    # Pattern: youtube.com/shorts/VIDEO_ID or /embed/VIDEO_ID
    match = re.search(r"(?:shorts|embed)/([\w-]{11})", url)
    if match:
        return match.group(1)

    logger.error(f"Could not extract video ID from: {url}")
    return None


def validate_clip_duration(duration: int, min_dur: int = 15, max_dur: int = 20) -> int:
    """
    Clamp and validate clip duration to allowed range.
    
    Returns the validated duration (clamped if out of bounds).
    """
    if duration < min_dur:
        logger.warning(f"Clip duration {duration}s below minimum, using {min_dur}s")
        return min_dur
    if duration > max_dur:
        logger.warning(f"Clip duration {duration}s above maximum, using {max_dur}s")
        return max_dur
    return duration
