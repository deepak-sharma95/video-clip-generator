"""
ClipGenius - Application Configuration
=======================================
Centralised configuration loaded from environment variables.
All settings are validated and have sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
# We resolve relative to this file so it works regardless of cwd
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)


class Config:
    """Application-wide configuration singleton."""

    # --- General ---
    APP_NAME: str = os.getenv("APP_NAME", "ClipGenius")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # --- Paths (resolved relative to project root) ---
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    TEMP_DIR: Path = PROJECT_ROOT / os.getenv("TEMP_DIR", "temp")
    OUTPUT_DIR: Path = PROJECT_ROOT / os.getenv("OUTPUT_DIR", "output")

    # --- Clip Settings ---
    DEFAULT_CLIP_DURATION: int = int(os.getenv("DEFAULT_CLIP_DURATION", "18"))
    MIN_CLIP_DURATION: int = int(os.getenv("MIN_CLIP_DURATION", "10"))
    MAX_CLIP_DURATION: int = int(os.getenv("MAX_CLIP_DURATION", "60"))
    MAX_CLIPS: int = int(os.getenv("MAX_CLIPS", "10"))

    # --- Download Settings ---
    MAX_VIDEO_DURATION: int = int(os.getenv("MAX_VIDEO_DURATION", "7200"))
    PREFERRED_RESOLUTION: int = int(os.getenv("PREFERRED_RESOLUTION", "1080"))

    # --- Audio Analysis Settings ---
    AUDIO_SAMPLE_RATE: int = 22050        # librosa default sample rate
    HOP_LENGTH: int = 512                  # Hop length for audio analysis
    ENERGY_WINDOW_SEC: float = 1.0         # Window size for energy computation (seconds)
    PEAK_MIN_DISTANCE_SEC: float = 10.0    # Minimum distance between detected peaks (seconds)

    @classmethod
    def ensure_dirs(cls) -> None:
        """Create required directories if they don't exist."""
        cls.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def summary(cls) -> dict:
        """Return a summary of current configuration for logging."""
        return {
            "app_name": cls.APP_NAME,
            "debug": cls.DEBUG,
            "log_level": cls.LOG_LEVEL,
            "temp_dir": str(cls.TEMP_DIR),
            "output_dir": str(cls.OUTPUT_DIR),
            "clip_duration": f"{cls.MIN_CLIP_DURATION}-{cls.MAX_CLIP_DURATION}s (default {cls.DEFAULT_CLIP_DURATION}s)",
            "max_clips": cls.MAX_CLIPS,
            "max_video_duration": f"{cls.MAX_VIDEO_DURATION}s ({cls.MAX_VIDEO_DURATION // 60} min)",
            "preferred_resolution": f"{cls.PREFERRED_RESOLUTION}p",
        }
