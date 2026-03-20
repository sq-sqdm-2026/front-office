"""
Front Office - Podcast Audio Generation
Converts podcast scripts to MP3 using macOS TTS (say command) + ffmpeg.
Each host gets a unique voice for natural conversation feel.
"""
import os
import re
import subprocess
import tempfile
from pathlib import Path
from ..database.db import query, execute

PODCAST_DIR = Path(__file__).parent.parent.parent / "static" / "podcasts"
PODCAST_DIR.mkdir(parents=True, exist_ok=True)

# Voice assignments for podcast hosts
VOICE_MAP = {
    "MIKE": "Daniel",      # Male, warm
    "LISA": "Samantha",     # Female, clear
    "EARL": "Alex",         # Male, deeper
}
DEFAULT_VOICE = "Samantha"


def _parse_script(script: str) -> list:
    """Parse podcast script into (host, dialogue) segments."""
    segments = []
    # Split by host markers: MIKE:, LISA:, EARL:
    pattern = r'(MIKE|LISA|EARL):\s*'
    parts = re.split(pattern, script)

    # parts alternates: [preamble, HOST, dialogue, HOST, dialogue, ...]
    i = 1  # skip preamble
    while i < len(parts) - 1:
        host = parts[i].strip()
        dialogue = parts[i + 1].strip()
        if dialogue:
            # Clean up dialogue
            dialogue = dialogue.replace('"', '').replace("'", "'")
            dialogue = re.sub(r'\s+', ' ', dialogue).strip()
            segments.append((host, dialogue))
        i += 2

    return segments


def _generate_segment_audio(host: str, text: str, output_path: str) -> bool:
    """Generate audio for a single segment using macOS say command."""
    voice = VOICE_MAP.get(host, DEFAULT_VOICE)
    try:
        subprocess.run(
            ["/usr/bin/say", "-v", voice, "-o", output_path, text],
            timeout=60,
            check=True,
            capture_output=True,
        )
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        print(f"TTS error for {host}: {e}")
        return False


async def generate_podcast_audio(episode_id: int, db_path: str = None) -> dict:
    """Generate MP3 audio for a podcast episode."""
    # Get episode
    episodes = query(
        "SELECT * FROM podcast_episodes WHERE id=?",
        (episode_id,), db_path=db_path
    )
    if not episodes:
        return {"success": False, "error": "Episode not found"}

    episode = episodes[0]
    script = episode.get("script", "")
    if not script:
        return {"success": False, "error": "Episode has no script"}

    # Parse script into segments
    segments = _parse_script(script)
    if not segments:
        return {"success": False, "error": "Could not parse script into segments"}

    # Generate audio segments in temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        segment_files = []

        for idx, (host, dialogue) in enumerate(segments):
            aiff_path = os.path.join(tmpdir, f"seg_{idx:03d}.aiff")
            if _generate_segment_audio(host, dialogue, aiff_path):
                segment_files.append(aiff_path)
            else:
                print(f"Skipping segment {idx} ({host}): TTS failed")

        if not segment_files:
            return {"success": False, "error": "No audio segments generated"}

        # Create concat file for ffmpeg
        concat_path = os.path.join(tmpdir, "concat.txt")
        with open(concat_path, "w") as f:
            for sf in segment_files:
                f.write(f"file '{sf}'\n")

        # Combine into MP3
        ep_num = episode.get("episode_number", episode_id)
        output_filename = f"episode_{ep_num}.mp3"
        output_path = str(PODCAST_DIR / output_filename)

        try:
            subprocess.run(
                [
                    "/opt/homebrew/bin/ffmpeg", "-y",
                    "-f", "concat", "-safe", "0",
                    "-i", concat_path,
                    "-acodec", "libmp3lame", "-q:a", "3",
                    output_path,
                ],
                timeout=120,
                check=True,
                capture_output=True,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            return {"success": False, "error": f"ffmpeg failed: {e}"}

    if not os.path.exists(output_path):
        return {"success": False, "error": "Output file not created"}

    # Get duration
    try:
        result = subprocess.run(
            ["/opt/homebrew/bin/ffmpeg", "-i", output_path],
            capture_output=True, text=True, timeout=10,
        )
        duration_match = re.search(r"Duration: (\d+):(\d+):(\d+)", result.stderr)
        duration_secs = 0
        if duration_match:
            h, m, s = int(duration_match.group(1)), int(duration_match.group(2)), int(duration_match.group(3))
            duration_secs = h * 3600 + m * 60 + s
    except Exception:
        duration_secs = 0

    # Update database
    try:
        execute(
            "ALTER TABLE podcast_episodes ADD COLUMN audio_file_path TEXT DEFAULT NULL",
            db_path=db_path,
        )
    except Exception:
        pass  # Column may already exist
    try:
        execute(
            "ALTER TABLE podcast_episodes ADD COLUMN audio_duration INTEGER DEFAULT NULL",
            db_path=db_path,
        )
    except Exception:
        pass

    execute(
        "UPDATE podcast_episodes SET audio_file_path=?, audio_duration=? WHERE id=?",
        (f"podcasts/{output_filename}", duration_secs, episode_id),
        db_path=db_path,
    )

    file_size = os.path.getsize(output_path) / (1024 * 1024)

    return {
        "success": True,
        "episode_id": episode_id,
        "download_url": f"/static/podcasts/{output_filename}",
        "duration_seconds": duration_secs,
        "file_size_mb": round(file_size, 1),
    }
