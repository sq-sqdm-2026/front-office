"""
Front Office - Podcast Audio Generation
Converts podcast scripts to MP3 using edge-tts (Microsoft Edge TTS) + ffmpeg.
Each host gets a unique voice for natural conversation feel.
Falls back to macOS TTS if edge-tts is not available.
"""
import asyncio
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from ..database.db import query, execute

PODCAST_DIR = Path(__file__).parent.parent.parent / "static" / "podcasts"
PODCAST_DIR.mkdir(parents=True, exist_ok=True)

# Edge TTS voice assignments (Microsoft Neural voices)
EDGE_VOICE_MAP = {
    "MIKE": "en-US-GuyNeural",        # Male, warm sports anchor
    "LISA": "en-US-JennyNeural",       # Female, clear analyst
    "EARL": "en-US-DavisNeural",       # Male, deeper color commentator
}

# macOS fallback voice assignments
MAC_VOICE_MAP = {
    "MIKE": "Daniel",
    "LISA": "Samantha",
    "EARL": "Alex",
}

DEFAULT_EDGE_VOICE = "en-US-JennyNeural"
DEFAULT_MAC_VOICE = "Samantha"


def _has_edge_tts() -> bool:
    """Check if edge-tts is available."""
    return shutil.which("edge-tts") is not None


def _has_ffmpeg() -> bool:
    """Check if ffmpeg is available."""
    return shutil.which("ffmpeg") is not None


def _parse_script(script: str) -> list:
    """Parse podcast script into (host, dialogue) segments."""
    segments = []
    pattern = r'(MIKE|LISA|EARL):\s*'
    parts = re.split(pattern, script)

    i = 1  # skip preamble
    while i < len(parts) - 1:
        host = parts[i].strip()
        dialogue = parts[i + 1].strip()
        if dialogue:
            dialogue = dialogue.replace('"', '').replace("'", "\u2019")
            dialogue = re.sub(r'\s+', ' ', dialogue).strip()
            segments.append((host, dialogue))
        i += 2

    return segments


async def _generate_segment_edge_tts(host: str, text: str, output_path: str) -> bool:
    """Generate audio for a single segment using edge-tts."""
    voice = EDGE_VOICE_MAP.get(host, DEFAULT_EDGE_VOICE)
    try:
        proc = await asyncio.create_subprocess_exec(
            "edge-tts", "--voice", voice, "--text", text,
            "--write-media", output_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except (asyncio.TimeoutError, Exception) as e:
        print(f"Edge TTS error for {host}: {e}")
        return False


def _generate_segment_mac_tts(host: str, text: str, output_path: str) -> bool:
    """Generate audio for a single segment using macOS say command."""
    voice = MAC_VOICE_MAP.get(host, DEFAULT_MAC_VOICE)
    say_path = "/usr/bin/say"
    if not os.path.exists(say_path):
        return False
    try:
        subprocess.run(
            [say_path, "-v", voice, "-o", output_path, text],
            timeout=60, check=True, capture_output=True,
        )
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        print(f"macOS TTS error for {host}: {e}")
        return False


async def generate_podcast_audio(episode_id: int, db_path: str = None) -> dict:
    """Generate MP3 audio for a podcast episode."""
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

    segments = _parse_script(script)
    if not segments:
        return {"success": False, "error": "Could not parse script into segments"}

    # Check for TTS availability
    use_edge = _has_edge_tts()
    if not use_edge and not os.path.exists("/usr/bin/say"):
        return {"success": False, "error": "No TTS engine available. Install edge-tts: pip install edge-tts"}

    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return {"success": False, "error": "ffmpeg not found. Install ffmpeg to generate audio."}

    # Generate audio segments in temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        segment_files = []
        ext = ".mp3" if use_edge else ".aiff"

        for idx, (host, dialogue) in enumerate(segments):
            seg_path = os.path.join(tmpdir, f"seg_{idx:03d}{ext}")
            if use_edge:
                ok = await _generate_segment_edge_tts(host, dialogue, seg_path)
            else:
                ok = _generate_segment_mac_tts(host, dialogue, seg_path)

            if ok:
                segment_files.append(seg_path)
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
                    ffmpeg_path, "-y",
                    "-f", "concat", "-safe", "0",
                    "-i", concat_path,
                    "-acodec", "libmp3lame", "-q:a", "3",
                    output_path,
                ],
                timeout=120, check=True, capture_output=True,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
            return {"success": False, "error": f"ffmpeg failed: {e}"}

    if not os.path.exists(output_path):
        return {"success": False, "error": "Output file not created"}

    # Get duration
    duration_secs = 0
    try:
        result = subprocess.run(
            [ffmpeg_path, "-i", output_path],
            capture_output=True, text=True, timeout=10,
        )
        duration_match = re.search(r"Duration: (\d+):(\d+):(\d+)", result.stderr)
        if duration_match:
            h, m, s = int(duration_match.group(1)), int(duration_match.group(2)), int(duration_match.group(3))
            duration_secs = h * 3600 + m * 60 + s
    except Exception:
        pass

    # Update database
    try:
        execute(
            "ALTER TABLE podcast_episodes ADD COLUMN audio_file_path TEXT DEFAULT NULL",
            db_path=db_path,
        )
    except Exception:
        pass
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
    tts_engine = "Edge TTS (Microsoft Neural)" if use_edge else "macOS TTS"

    return {
        "success": True,
        "episode_id": episode_id,
        "download_url": f"/static/podcasts/{output_filename}",
        "duration_seconds": duration_secs,
        "file_size_mb": round(file_size, 1),
        "tts_engine": tts_engine,
    }
