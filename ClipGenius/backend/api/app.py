import time
import threading
import traceback
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from loguru import logger

from backend.config import Config
from backend.utils.logger import setup_logger
from backend.utils.validators import is_valid_youtube_url, validate_clip_duration
from backend.utils.file_manager import FileManager
from backend.services.downloader import Downloader, DownloadError
from backend.analysis.audio_energy import AudioEnergyAnalyzer
from backend.analysis.scorer import Scorer
from backend.services.clip_generator import ClipGenerator, ClipGeneratorError

app = Flask(__name__, static_folder="../../frontend", static_url_path="/")
CORS(app)

# Global dictionary to hold job status
# Format: { "job_id": {"status": "running|completed|error", "progress": "step name", "results": [], "error": ""} }
jobs = {}

def process_video_job(job_id, url, clip_duration, max_clips, aspect_ratio):
    """Background task to process the video."""
    start_time = time.time()
    
    jobs[job_id] = {
        "status": "running",
        "progress": "Initializing...",
        "results": [],
        "error": None
    }
    
    file_mgr = FileManager(job_id=job_id)
    downloader = Downloader()
    analyzer = AudioEnergyAnalyzer()
    scorer = Scorer(clip_duration=clip_duration, max_clips=max_clips)
    clip_gen = ClipGenerator()

    try:
        # Step 1: Fetch Video Info
        jobs[job_id]["progress"] = "Fetching video info..."
        info = downloader.get_video_info(url)
        
        # Step 2: Download Video
        jobs[job_id]["progress"] = f"Downloading video '{info['title']}'..."
        video_path = downloader.download_video(url, file_mgr.video_path)
        
        # Step 3: Extract Audio
        jobs[job_id]["progress"] = "Extracting audio for analysis..."
        audio_path = downloader.extract_audio(video_path, file_mgr.audio_path)
        
        # Step 4: Analyse Audio Energy
        jobs[job_id]["progress"] = "Analysing audio energy..."
        frames = analyzer.analyze(audio_path)
        
        # Step 5: Find Viral Moments
        jobs[job_id]["progress"] = "Finding viral moments..."
        moments = scorer.find_viral_moments(frames, info["duration"])
        
        if not moments:
            jobs[job_id]["status"] = "completed"
            jobs[job_id]["progress"] = "No viral moments detected."
            file_mgr.cleanup_temp()
            return
            
        # Step 6: Generate Clips
        jobs[job_id]["progress"] = f"Generating {len(moments)} clips (Format: {aspect_ratio})..."
        clips = clip_gen.generate_clips(video_path, moments, file_mgr.job_id, aspect_ratio=aspect_ratio)
        
        # Clean up temp files (leaves output files intact)
        file_mgr.cleanup_temp()
        
        # Format results for the frontend
        formatted_results = []
        for clip in clips:
            clip_name = Path(clip["path"]).name
            formatted_results.append({
                "rank": clip["rank"],
                "start": clip["start_timestamp"],
                "end": clip["end_timestamp"],
                "duration": clip["duration"],
                "score": clip["viral_score"],
                "reason": clip["reason"],
                "size_mb": clip["size_mb"],
                "url": f"/api/clips/{clip_name}"
            })
            
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = "Done!"
        jobs[job_id]["results"] = formatted_results
        
        logger.info(f"Job {job_id} completed successfully in {time.time() - start_time:.1f}s")
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}\n{traceback.format_exc()}")
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
        file_mgr.cleanup_temp()


@app.route("/")
def serve_frontend():
    """Serve the main frontend HTML file."""
    return app.send_static_file("index.html")

@app.route("/api/extract", methods=["POST"])
def extract_clips():
    """Start a new clip extraction job."""
    data = request.json
    if not data or "url" not in data:
        return jsonify({"error": "Missing YouTube URL"}), 400
        
    url = data["url"]
    if not is_valid_youtube_url(url):
        return jsonify({"error": "Invalid YouTube URL"}), 400
        
    clip_duration = validate_clip_duration(
        data.get("duration", Config.DEFAULT_CLIP_DURATION),
        Config.MIN_CLIP_DURATION, 
        Config.MAX_CLIP_DURATION
    )
    max_clips = data.get("clips", Config.MAX_CLIPS)
    aspect_ratio = data.get("format", "16:9")
    
    job_id = f"job_{int(time.time())}"
    
    # Start processing in a background thread
    thread = threading.Thread(
        target=process_video_job, 
        args=(job_id, url, clip_duration, max_clips, aspect_ratio)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        "job_id": job_id,
        "message": "Extraction job started successfully"
    })

@app.route("/api/status/<job_id>", methods=["GET"])
def get_status(job_id):
    """Check the status of a running job."""
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
        
    return jsonify(jobs[job_id])

@app.route("/api/clips/<filename>", methods=["GET"])
def serve_clip(filename):
    """Serve a generated video clip."""
    return send_from_directory(Config.OUTPUT_DIR.absolute(), filename)

def start_api():
    setup_logger()
    Config.ensure_dirs()
    logger.info("Starting ClipGenius API on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)

if __name__ == "__main__":
    start_api()
