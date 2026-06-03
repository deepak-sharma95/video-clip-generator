"""
ClipGenius - Temporary File Manager
=====================================
Handles creation, tracking, and cleanup of temporary files
generated during video download and analysis.
"""

import time
import shutil
from pathlib import Path
from loguru import logger

from backend.config import Config


class FileManager:
    """
    Manages temporary and output files for a single processing job.
    
    Each job gets its own subdirectory inside temp/ to keep things isolated.
    Cleanup removes the entire job directory when processing is done.
    """

    def __init__(self, job_id: str | None = None):
        """
        Initialise the file manager for a specific job.

        Args:
            job_id: Unique identifier for this job. Auto-generated if not provided.
        """
        self.job_id = job_id or f"job_{int(time.time())}"
        self.job_dir = Config.TEMP_DIR / self.job_id
        self._created_files: list[Path] = []

        # Ensure directories exist
        Config.ensure_dirs()
        self.job_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(f"FileManager initialised — job_id={self.job_id}, dir={self.job_dir}")

    @property
    def video_path(self) -> Path:
        """Path where the downloaded video will be stored."""
        return self.job_dir / "source_video.mp4"

    @property
    def audio_path(self) -> Path:
        """Path where the extracted audio will be stored."""
        return self.job_dir / "source_audio.wav"

    def clip_path(self, index: int) -> Path:
        """
        Generate output path for a clip file.

        Args:
            index: Clip number (1-based).

        Returns:
            Path in the output directory.
        """
        return Config.OUTPUT_DIR / f"{self.job_id}_clip_{index:02d}.mp4"

    def register_file(self, path: Path) -> None:
        """Track a file for potential cleanup later."""
        self._created_files.append(path)
        logger.debug(f"Registered file: {path}")

    def cleanup_temp(self) -> None:
        """
        Remove the entire temporary job directory.
        
        Output clips in output/ are preserved — only temp files are removed.
        """
        if self.job_dir.exists():
            shutil.rmtree(self.job_dir, ignore_errors=True)
            logger.info(f"Cleaned up temp directory: {self.job_dir}")
        else:
            logger.debug(f"Temp directory already removed: {self.job_dir}")

    def cleanup_all(self) -> None:
        """Remove both temp files and generated output clips."""
        self.cleanup_temp()

        # Remove output clips
        for f in self._created_files:
            if f.exists():
                f.unlink()
                logger.debug(f"Removed output file: {f}")

        self._created_files.clear()
        logger.info(f"Full cleanup complete for job {self.job_id}")

    def get_temp_size_mb(self) -> float:
        """Calculate total size of temp files in MB."""
        if not self.job_dir.exists():
            return 0.0
        total = sum(f.stat().st_size for f in self.job_dir.rglob("*") if f.is_file())
        return total / (1024 * 1024)
