"""
Front Office - Podcast Audio Generation
Converts podcast scripts to MP3 using Orpheus TTS 3B via Ollama + SNAC decoder.
Each host gets a unique voice for natural, emotive conversation.
Requires: ollama pull orpheus-3b, pip install snac torch, ffmpeg
"""
import asyncio
import os
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

import httpx

from ..database.db import query, execute

PODCAST_DIR = Path(__file__).parent.parent.parent / "static" / "podcasts"
PODCAST_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
ORPHEUS_MODEL = os.environ.get("ORPHEUS_MODEL", "orpheus-3b")

# Orpheus voice assignments (natural, emotive voices)
VOICE_MAP = {
    "MIKE": "dan",    # Male, warm sports anchor
    "LISA": "tara",   # Female, clear analyst
    "EARL": "leo",    # Male, deeper color commentator
}
DEFAULT_VOICE = "tara"

# Audio token parsing
AUDIO_TOKEN_RE = re.compile(r"<custom_token_(\d+)>")
SNAC_BASE_OFFSET = 10  # First 10 custom tokens are control tokens
SAMPLE_RATE = 24000


def _has_ffmpeg() -> bool:
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


def _load_snac():
    """Lazily load SNAC decoder. Returns (snac_model, torch) or raises."""
    try:
        import torch
        from snac import SNAC
    except ImportError:
        raise RuntimeError(
            "Orpheus TTS requires PyTorch and SNAC. Install with: "
            "pip install snac torch"
        )
    model = SNAC.from_pretrained("hubertsiuzdak/snac_24khz")
    model.eval()
    return model, torch


def _decode_audio_tokens(token_text: str, snac_model, torch):
    """Parse Orpheus custom_token output and decode to audio via SNAC."""
    token_ids = [int(m) for m in AUDIO_TOKEN_RE.findall(token_text)]
    if not token_ids:
        return None

    # Convert to audio token indices (skip control tokens)
    audio_ids = [t - SNAC_BASE_OFFSET for t in token_ids]

    # Trim to multiple of 7 (one SNAC frame = 7 tokens)
    n = len(audio_ids) // 7 * 7
    if n == 0:
        return None
    audio_ids = audio_ids[:n]

    # Redistribute across 3 SNAC codebook layers
    codes_0, codes_1, codes_2 = [], [], []
    for i in range(0, n, 7):
        codes_0.append(audio_ids[i])
        codes_1.append(audio_ids[i + 1] - 4096)
        codes_1.append(audio_ids[i + 4] - 4096)
        codes_2.append(audio_ids[i + 2] - 8192)
        codes_2.append(audio_ids[i + 3] - 8192)
        codes_2.append(audio_ids[i + 5] - 8192)
        codes_2.append(audio_ids[i + 6] - 8192)

    with torch.inference_mode():
        codes = [
            torch.tensor(codes_0).unsqueeze(0),
            torch.tensor(codes_1).unsqueeze(0),
            torch.tensor(codes_2).unsqueeze(0),
        ]
        audio = snac_model.decode(codes)

    # Convert to numpy array
    audio_np = audio.squeeze().cpu().numpy()
    return audio_np


def _save_wav(audio_np, path: str):
    """Save numpy audio array as 16-bit WAV file."""
    import numpy as np
    # Normalize to int16 range
    audio_np = np.clip(audio_np, -1.0, 1.0)
    audio_int16 = (audio_np * 32767).astype(np.int16)
    raw_bytes = audio_int16.tobytes()

    # Write WAV header + data
    num_samples = len(audio_int16)
    data_size = num_samples * 2  # 16-bit = 2 bytes per sample
    with open(path, "wb") as f:
        # RIFF header
        f.write(b"RIFF")
        f.write(struct.pack("<I", 36 + data_size))
        f.write(b"WAVE")
        # fmt chunk
        f.write(b"fmt ")
        f.write(struct.pack("<I", 16))       # chunk size
        f.write(struct.pack("<H", 1))        # PCM
        f.write(struct.pack("<H", 1))        # mono
        f.write(struct.pack("<I", SAMPLE_RATE))
        f.write(struct.pack("<I", SAMPLE_RATE * 2))  # byte rate
        f.write(struct.pack("<H", 2))        # block align
        f.write(struct.pack("<H", 16))       # bits per sample
        # data chunk
        f.write(b"data")
        f.write(struct.pack("<I", data_size))
        f.write(raw_bytes)


async def _generate_segment_orpheus(voice: str, text: str, output_path: str,
                                     snac_model, torch) -> bool:
    """Generate audio for a segment using Orpheus TTS via Ollama."""
    payload = {
        "model": ORPHEUS_MODEL,
        "prompt": f"{voice}: {text}",
        "stream": False,
        "options": {
            "temperature": 0.6,
            "repetition_penalty": 1.1,
            "num_predict": 4096,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE}/api/generate", json=payload
            )
            resp.raise_for_status()
            response_text = resp.json().get("response", "")

        if not response_text or "<custom_token_" not in response_text:
            print(f"Orpheus returned no audio tokens for: {text[:50]}...")
            return False

        audio_np = _decode_audio_tokens(response_text, snac_model, torch)
        if audio_np is None or len(audio_np) < SAMPLE_RATE // 10:
            print(f"Orpheus decoded too little audio for: {text[:50]}...")
            return False

        _save_wav(audio_np, output_path)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0

    except Exception as e:
        print(f"Orpheus TTS error: {e}")
        return False


async def generate_podcast_audio(episode_id: int, db_path: str = None) -> dict:
    """Generate MP3 audio for a podcast episode using Orpheus TTS."""
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

    # Check Orpheus model availability
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            if not any("orpheus" in m.lower() for m in models):
                return {
                    "success": False,
                    "error": f"Orpheus TTS model not found. Install with: ollama pull {ORPHEUS_MODEL}"
                }
    except Exception as e:
        return {"success": False, "error": f"Ollama not reachable: {e}"}

    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return {"success": False, "error": "ffmpeg not found. Install ffmpeg to generate audio."}

    # Load SNAC decoder
    try:
        snac_model, torch = _load_snac()
    except RuntimeError as e:
        return {"success": False, "error": str(e)}

    # Generate audio segments in temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        segment_files = []

        for idx, (host, dialogue) in enumerate(segments):
            seg_path = os.path.join(tmpdir, f"seg_{idx:03d}.wav")
            voice = VOICE_MAP.get(host, DEFAULT_VOICE)
            ok = await _generate_segment_orpheus(voice, dialogue, seg_path,
                                                  snac_model, torch)
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

    return {
        "success": True,
        "episode_id": episode_id,
        "download_url": f"/static/podcasts/{output_filename}",
        "duration_seconds": duration_secs,
        "file_size_mb": round(file_size, 1),
        "tts_engine": "Orpheus TTS 3B (via Ollama)",
    }
