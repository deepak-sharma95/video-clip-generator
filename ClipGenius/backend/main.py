"""
ClipGenius - Main Entry Point (Phase 1: CLI)
===============================================
Command-line interface for extracting viral clips from YouTube videos.

Usage:
    python -m backend.main <youtube_url> [--duration 18] [--clips 3]
"""

import sys
import time
import argparse

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from backend.config import Config
from backend.utils.logger import setup_logger, logger
from backend.utils.validators import is_valid_youtube_url, validate_clip_duration
from backend.utils.file_manager import FileManager
from backend.services.downloader import Downloader, DownloadError
from backend.analysis.audio_energy import AudioEnergyAnalyzer
from backend.analysis.scorer import Scorer
from backend.services.clip_generator import ClipGenerator, ClipGeneratorError

# Rich console for beautiful CLI output
console = Console()


def print_banner():
    """Display the ClipGenius startup banner."""
    banner = """
 ██████╗██╗     ██╗██████╗  ██████╗ ███████╗███╗   ██╗██╗██╗   ██╗███████╗
██╔════╝██║     ██║██╔══██╗██╔════╝ ██╔════╝████╗  ██║██║██║   ██║██╔════╝
██║     ██║     ██║██████╔╝██║  ███╗█████╗  ██╔██╗ ██║██║██║   ██║███████╗
██║     ██║     ██║██╔═══╝ ██║   ██║██╔══╝  ██║╚██╗██║██║██║   ██║╚════██║
╚██████╗███████╗██║██║     ╚██████╔╝███████╗██║ ╚████║██║╚██████╔╝███████║
 ╚═════╝╚══════╝╚═╝╚═╝      ╚═════╝ ╚══════╝╚═╝  ╚═══╝╚═╝ ╚═════╝ ╚══════╝
    """
    console.print(banner, style="bold cyan")
    console.print("  YouTube Viral Clip Extractor v0.1.0", style="dim")
    console.print("  Phase 1: Audio Energy Based Detection\n", style="dim")


def run_pipeline(url: str, clip_duration: int, max_clips: int):
    """
    Execute the full ClipGenius pipeline.

    Steps:
        1. Validate input
        2. Fetch video info
        3. Download video
        4. Extract audio
        5. Analyse audio energy
        6. Score and find viral moments
        7. Generate clips
        8. Cleanup temp files
    """
    start_time = time.time()

    # Initialise components
    file_mgr = FileManager()
    downloader = Downloader()
    analyzer = AudioEnergyAnalyzer()
    scorer = Scorer(clip_duration=clip_duration, max_clips=max_clips)
    clip_gen = ClipGenerator()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:

            # --- Step 1: Fetch Video Info ---
            task = progress.add_task("Fetching video info...", total=None)
            info = downloader.get_video_info(url)
            progress.update(task, completed=True)

            console.print(Panel(
                f"[bold]{info['title']}[/bold]\n"
                f"By: {info['uploader']} | Duration: {info['duration']}s | "
                f"Views: {info.get('view_count', 'N/A')}",
                title="📹 Video Found",
                border_style="green",
            ))

            # --- Step 2: Download Video ---
            task = progress.add_task("Downloading video...", total=None)
            video_path = downloader.download_video(url, file_mgr.video_path)
            progress.update(task, completed=True)
            console.print(f"  ✅ Video downloaded: {file_mgr.get_temp_size_mb():.1f} MB")

            # --- Step 3: Extract Audio ---
            task = progress.add_task("Extracting audio...", total=None)
            audio_path = downloader.extract_audio(video_path, file_mgr.audio_path)
            progress.update(task, completed=True)
            console.print("  ✅ Audio extracted")

            # --- Step 4: Analyse Audio Energy ---
            task = progress.add_task("Analysing audio energy...", total=None)
            frames = analyzer.analyze(audio_path)
            progress.update(task, completed=True)
            console.print(f"  ✅ Energy analysis complete: {len(frames)} seconds analysed")

            # --- Step 5: Find Viral Moments ---
            task = progress.add_task("Finding viral moments...", total=None)
            moments = scorer.find_viral_moments(frames, info["duration"])
            progress.update(task, completed=True)

            if not moments:
                console.print("\n[yellow]⚠️  No viral moments detected in this video.[/yellow]")
                return

            console.print(f"  ✅ Found {len(moments)} viral moment(s)")

            # --- Step 6: Generate Clips ---
            task = progress.add_task("Generating clips...", total=len(moments))
            clips = clip_gen.generate_clips(video_path, moments, file_mgr.job_id)
            progress.update(task, completed=len(moments))

        # --- Results ---
        elapsed = time.time() - start_time
        _print_results(clips, elapsed)

    except (DownloadError, ClipGeneratorError) as e:
        console.print(f"\n[red]❌ Error: {e}[/red]")
        logger.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Cancelled by user[/yellow]")
        sys.exit(0)
    finally:
        # Cleanup temp files (keep output clips)
        file_mgr.cleanup_temp()


def _print_results(clips: list[dict], elapsed: float):
    """Display the final results in a beautiful table."""
    console.print("\n")
    console.print(Panel(
        f"[bold green]Processing complete in {elapsed:.1f} seconds[/bold green]",
        title="🎬 ClipGenius Results",
        border_style="green",
    ))

    # Results table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Time Range", width=16)
    table.add_column("Duration", width=10)
    table.add_column("Viral Score", width=12)
    table.add_column("Reason", width=40)
    table.add_column("Size", width=8)

    for clip in clips:
        score = clip["viral_score"]
        score_color = "green" if score > 0.8 else "yellow" if score > 0.5 else "red"

        table.add_row(
            str(clip["rank"]),
            f"{clip['start_timestamp']} → {clip['end_timestamp']}",
            f"{clip['duration']:.0f}s",
            f"[{score_color}]{score:.1%}[/{score_color}]",
            clip["reason"][:40],
            f"{clip['size_mb']:.1f}MB",
        )

    console.print(table)

    # Output paths
    console.print("\n📁 [bold]Clip files saved to:[/bold]")
    for clip in clips:
        console.print(f"   → {clip['path']}")
    console.print()


def main():
    """CLI entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="ClipGenius — Extract viral clips from YouTube videos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("url", help="YouTube video URL")
    parser.add_argument(
        "--duration", "-d",
        type=int,
        default=Config.DEFAULT_CLIP_DURATION,
        help=f"Clip duration in seconds (default: {Config.DEFAULT_CLIP_DURATION})",
    )
    parser.add_argument(
        "--clips", "-c",
        type=int,
        default=Config.MAX_CLIPS,
        help=f"Number of clips to extract (default: {Config.MAX_CLIPS})",
    )

    args = parser.parse_args()

    # Setup
    print_banner()
    setup_logger()
    Config.ensure_dirs()

    # Validate URL
    if not is_valid_youtube_url(args.url):
        console.print(f"[red]❌ Invalid YouTube URL: {args.url}[/red]")
        sys.exit(1)

    # Validate duration
    duration = validate_clip_duration(
        args.duration, Config.MIN_CLIP_DURATION, Config.MAX_CLIP_DURATION
    )

    # Show config
    console.print(Panel(
        f"URL: {args.url}\n"
        f"Clip Duration: {duration}s\n"
        f"Max Clips: {args.clips}",
        title="⚙️  Configuration",
        border_style="blue",
    ))

    # Run the pipeline
    run_pipeline(args.url, duration, args.clips)


if __name__ == "__main__":
    main()
