"""
ClipGenius - Video Clip Generator
===================================
Extracts video segments using MoviePy based on detected viral moments.
Handles encoding, quality settings, and output file management.
"""

from pathlib import Path
from loguru import logger

from backend.config import Config
from backend.analysis.scorer import ViralMoment


class ClipGeneratorError(Exception):
    """Raised when clip generation fails."""
    pass


class ClipGenerator:
    """
    Generates short video clips from a source video at specified timestamps.
    Uses MoviePy (backed by FFmpeg) for precise cutting and encoding.
    """

    def generate_clips(
        self,
        video_path: Path,
        moments: list[ViralMoment],
        job_id: str,
        aspect_ratio: str = "16:9"
    ) -> list[dict]:
        """
        Generate clip files for each detected viral moment.

        Args:
            video_path: Path to the source video file.
            moments: List of ViralMoment objects with timestamps.
            job_id: Job identifier for output file naming.

        Returns:
            List of dicts with clip metadata (path, start, end, score).
        """
        if not video_path.exists():
            raise ClipGeneratorError(f"Source video not found: {video_path}")

        if not moments:
            logger.warning("No viral moments to generate clips for")
            return []

        Config.ensure_dirs()
        logger.info(f"Generating {len(moments)} clips from: {video_path}")

        # Import moviepy here to defer the heavy import
        from moviepy import VideoFileClip

        clips_info = []

        try:
            source = VideoFileClip(str(video_path))
            logger.info(f"Source video loaded: {source.duration:.1f}s, {source.size}")

            for moment in moments:
                try:
                    clip_info = self._extract_single_clip(
                        source, moment, job_id, aspect_ratio
                    )
                    clips_info.append(clip_info)
                except Exception as e:
                    logger.error(f"Failed to generate clip #{moment.rank}: {e}")
                    continue

            source.close()

        except Exception as e:
            raise ClipGeneratorError(f"Failed to load source video: {e}")

        logger.info(f"Successfully generated {len(clips_info)}/{len(moments)} clips")
        return clips_info

    def _extract_single_clip(
        self,
        source,
        moment: ViralMoment,
        job_id: str,
        aspect_ratio: str
    ) -> dict:
        """Extract a single clip from the source video."""
        output_path = Config.OUTPUT_DIR / f"{job_id}_clip_{moment.rank:02d}.mp4"

        logger.info(
            f"Extracting clip #{moment.rank}: "
            f"{moment.start_timestamp} → {moment.end_timestamp} "
            f"(score={moment.viral_score:.3f})"
        )

        # Clamp timestamps to video bounds
        start = max(0, moment.start_time)
        end = min(source.duration, moment.end_time)

        # Extract the subclip
        clip = source.subclipped(start, end)
        
        # Apply 9:16 Mobile crop if requested
        if aspect_ratio == "9:16":
            w, h = clip.w, clip.h
            target_w = int(h * 9 / 16)
            if target_w < w:
                x1 = int((w - target_w) / 2)
                x2 = x1 + target_w
                clip = clip.cropped(x1=x1, y1=0, x2=x2, y2=h)

        # Write the clip with high quality settings
        clip.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            bitrate="8000k",
            audio_bitrate="192k",
            preset="fast",
            temp_audiofile=str(Config.TEMP_DIR / f"temp_audio_{moment.rank}.m4a"),
            remove_temp=True,
            logger=None,  # Suppress moviepy's verbose output
        )

        clip.close()

        size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"Clip #{moment.rank} saved: {output_path} ({size_mb:.1f} MB)")

        return {
            "rank": moment.rank,
            "path": str(output_path),
            "start_time": moment.start_time,
            "end_time": moment.end_time,
            "start_timestamp": moment.start_timestamp,
            "end_timestamp": moment.end_timestamp,
            "duration": moment.duration,
            "viral_score": moment.viral_score,
            "reason": moment.reason,
            "size_mb": round(size_mb, 2),
        }
