"""
ClipGenius - YouTube Download Service
=======================================
Downloads YouTube videos and extracts audio using yt-dlp.
Handles format selection, progress tracking, and error recovery.
"""

import subprocess
from pathlib import Path
from loguru import logger

try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FFMPEG_PATH = "ffmpeg"  # Fallback to system PATH

from backend.config import Config
from backend.utils.validators import is_valid_youtube_url


class DownloadError(Exception):
    """Raised when video download fails."""
    pass


class Downloader:
    """
    Downloads YouTube videos and extracts audio tracks.

    Uses yt-dlp (a maintained fork of youtube-dl) for reliable
    downloading across different video formats and regions.
    """

    def __init__(self):
        self._verify_dependencies()

    def _verify_dependencies(self) -> None:
        """Check that yt-dlp and ffmpeg are available."""
        # Check yt-dlp
        try:
            subprocess.run(
                ["yt-dlp", "--version"],
                capture_output=True, text=True, check=True,
            )
            logger.debug("Dependency verified: yt-dlp")
        except FileNotFoundError:
            raise DownloadError(
                "'yt-dlp' is not installed or not in PATH. "
                "Please install it: pip install yt-dlp"
            )
        except subprocess.CalledProcessError:
            logger.debug("Dependency found (non-zero exit): yt-dlp")

        # Check ffmpeg (from imageio_ffmpeg or system PATH)
        try:
            subprocess.run(
                [FFMPEG_PATH, "-version"],
                capture_output=True, text=True, check=True,
            )
            logger.debug(f"Dependency verified: ffmpeg at {FFMPEG_PATH}")
        except FileNotFoundError:
            raise DownloadError(
                "'ffmpeg' is not found. Install via: pip install imageio-ffmpeg"
            )
        except subprocess.CalledProcessError:
            logger.debug(f"Dependency found (non-zero exit): ffmpeg at {FFMPEG_PATH}")

    def get_video_info(self, url: str) -> dict:
        """
        Fetch metadata about a YouTube video without downloading it.

        Args:
            url: YouTube video URL.

        Returns:
            Dictionary with keys: title, duration, uploader, thumbnail, video_id.
        
        Raises:
            DownloadError: If metadata extraction fails.
        """
        if not is_valid_youtube_url(url):
            raise DownloadError(f"Invalid YouTube URL: {url}")

        logger.info(f"Fetching video info: {url}")

        try:
            result = subprocess.run(
                [
                    "yt-dlp",
                    "--dump-json",
                    "--no-download",
                    "--no-warnings",
                    url,
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )

            import json
            data = json.loads(result.stdout)

            info = {
                "title": data.get("title", "Unknown"),
                "duration": data.get("duration", 0),
                "uploader": data.get("uploader", "Unknown"),
                "thumbnail": data.get("thumbnail", ""),
                "video_id": data.get("id", ""),
                "view_count": data.get("view_count", 0),
                "description": data.get("description", "")[:500],
            }

            logger.info(
                f"Video info fetched: \"{info['title']}\" "
                f"({info['duration']}s) by {info['uploader']}"
            )

            # Validate duration
            if info["duration"] > Config.MAX_VIDEO_DURATION:
                raise DownloadError(
                    f"Video is too long ({info['duration']}s). "
                    f"Maximum allowed: {Config.MAX_VIDEO_DURATION}s "
                    f"({Config.MAX_VIDEO_DURATION // 60} minutes)."
                )

            if info["duration"] < Config.MIN_CLIP_DURATION:
                raise DownloadError(
                    f"Video is too short ({info['duration']}s). "
                    f"Minimum required: {Config.MIN_CLIP_DURATION}s."
                )

            return info

        except subprocess.TimeoutExpired:
            raise DownloadError("Timed out fetching video info. Check your internet connection.")
        except subprocess.CalledProcessError as e:
            raise DownloadError(f"Failed to fetch video info: {e.stderr}")
        except Exception as e:
            raise DownloadError(f"Unexpected error fetching video info: {e}")

    def download_video(self, url: str, output_path: Path) -> Path:
        """
        Download the YouTube video in the best available quality (up to configured resolution).

        Args:
            url: YouTube video URL.
            output_path: Where to save the downloaded video file.

        Returns:
            Path to the downloaded video file.

        Raises:
            DownloadError: If download fails.
        """
        if not is_valid_youtube_url(url):
            raise DownloadError(f"Invalid YouTube URL: {url}")

        logger.info(f"Downloading video: {url}")
        logger.info(f"Output path: {output_path}")

        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Build format selector — pre-merged format to avoid needing ffprobe
            format_spec = "best[ext=mp4]/best"

            cmd = [
                "yt-dlp",
                "-f", format_spec,
                "--merge-output-format", "mp4",
                "--ffmpeg-location", str(Path(FFMPEG_PATH).parent),
                "-o", str(output_path),
                "--no-playlist",
                "--no-warnings",
                "--progress",
                "--newline",
                url,
            ]

            logger.debug(f"Running command: {' '.join(cmd)}")

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes timeout
            )

            if process.returncode != 0:
                raise DownloadError(f"yt-dlp failed: {process.stderr}")

            # yt-dlp sometimes appends extensions — find the actual file
            actual_path = self._find_downloaded_file(output_path)

            if not actual_path.exists():
                raise DownloadError(f"Download completed but file not found at: {actual_path}")

            size_mb = actual_path.stat().st_size / (1024 * 1024)
            logger.info(f"Video downloaded successfully: {actual_path} ({size_mb:.1f} MB)")

            return actual_path

        except subprocess.TimeoutExpired:
            raise DownloadError("Download timed out after 5 minutes.")
        except DownloadError:
            raise
        except Exception as e:
            raise DownloadError(f"Unexpected download error: {e}")

    def extract_audio(self, video_path: Path, audio_path: Path) -> Path:
        """
        Extract audio track from video file as WAV.

        Uses FFmpeg to extract and convert audio to WAV format
        at the sample rate expected by librosa.

        Args:
            video_path: Path to the source video.
            audio_path: Where to save the extracted audio.

        Returns:
            Path to the extracted audio file.

        Raises:
            DownloadError: If audio extraction fails.
        """
        if not video_path.exists():
            raise DownloadError(f"Video file not found: {video_path}")

        logger.info(f"Extracting audio from: {video_path}")

        audio_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            cmd = [
                FFMPEG_PATH,
                "-i", str(video_path),
                "-vn",                          # No video
                "-acodec", "pcm_s16le",         # WAV format
                "-ar", str(Config.AUDIO_SAMPLE_RATE),  # Sample rate
                "-ac", "1",                     # Mono
                "-y",                           # Overwrite
                str(audio_path),
            ]

            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if process.returncode != 0:
                raise DownloadError(f"FFmpeg audio extraction failed: {process.stderr[-500:]}")

            if not audio_path.exists():
                raise DownloadError(f"Audio extraction completed but file not found: {audio_path}")

            size_mb = audio_path.stat().st_size / (1024 * 1024)
            logger.info(f"Audio extracted successfully: {audio_path} ({size_mb:.1f} MB)")

            return audio_path

        except subprocess.TimeoutExpired:
            raise DownloadError("Audio extraction timed out.")
        except DownloadError:
            raise
        except Exception as e:
            raise DownloadError(f"Unexpected audio extraction error: {e}")

    def _find_downloaded_file(self, expected_path: Path) -> Path:
        """
        Locate the actual downloaded file.
        
        yt-dlp may add/change extensions, so we search for variations.
        """
        if expected_path.exists():
            return expected_path

        # Check common alternative extensions
        for ext in [".mp4", ".mkv", ".webm", ".mp4.part"]:
            alt = expected_path.with_suffix(ext)
            if alt.exists():
                logger.debug(f"Found file with alternative extension: {alt}")
                return alt

        # Search the parent directory for any video file
        parent = expected_path.parent
        stem = expected_path.stem
        for f in parent.iterdir():
            if f.stem.startswith(stem) and f.suffix in (".mp4", ".mkv", ".webm"):
                logger.debug(f"Found file by stem match: {f}")
                return f

        return expected_path  # Return original, will fail existence check upstream
