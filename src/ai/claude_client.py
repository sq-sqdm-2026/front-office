"""
Front Office - Claude CLI Client
Routes all text generation through Claude Code CLI (Max subscription).
Replaces ollama_client.py for all text generation tasks.

Ollama is still used for:
- Image generation (player portraits)
- Text-to-speech (podcast audio)
- ESPN highlight show (video pipeline)
"""
import subprocess
import json
import asyncio
import logging
from collections import deque
from datetime import datetime

logger = logging.getLogger("front_office.llm")

# Track LLM calls for the UI status indicator
_llm_failures: deque = deque(maxlen=50)
_llm_stats = {"calls": 0, "failures": 0, "last_failure": None, "provider": "claude-cli"}


def get_llm_failures(since: str = None) -> list:
    """Return recent LLM failures, optionally since a timestamp."""
    if since:
        return [f for f in _llm_failures if f["time"] > since]
    return list(_llm_failures)


def get_llm_stats() -> dict:
    """Return LLM call statistics."""
    return dict(_llm_stats)


def _record_failure(task_type: str, error: str):
    """Record an LLM failure for UI reporting."""
    failure = {
        "time": datetime.now().isoformat(),
        "task_type": task_type,
        "model": "claude-cli",
        "error": str(error),
    }
    _llm_failures.append(failure)
    _llm_stats["failures"] += 1
    _llm_stats["last_failure"] = failure
    logger.warning("Claude CLI call failed [%s]: %s", task_type, error)


def _call_claude(prompt: str, system_prompt: str = None, max_tokens: int = 1024) -> str:
    """Call Claude via CLI subprocess. Synchronous — use in async wrapper."""
    cmd = ["claude", "-p", prompt, "--model", "sonnet"]

    if system_prompt:
        cmd.extend(["--system-prompt", system_prompt])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            env=None,  # inherit parent env
        )
        if result.returncode != 0:
            error = result.stderr.strip() or f"Exit code {result.returncode}"
            raise RuntimeError(error)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        raise RuntimeError("Claude CLI timed out (120s)")
    except FileNotFoundError:
        raise RuntimeError("claude CLI not found — is Claude Code installed?")


async def generate(prompt: str, task_type: str = "creative",
                   system_prompt: str = None, temperature: float = 0.7,
                   max_tokens: int = 1024) -> str:
    """Send a prompt to Claude CLI and return the response text.
    Runs in a thread pool to avoid blocking the event loop.
    """
    _llm_stats["calls"] += 1

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, _call_claude, prompt, system_prompt, max_tokens
        )
        return result
    except Exception as e:
        _record_failure(task_type, e)
        return f"[LLM unavailable: {e}]"


async def generate_json(prompt: str, task_type: str = "strategic",
                        system_prompt: str = None) -> dict:
    """Generate a structured JSON response from Claude."""
    full_prompt = prompt + "\n\nRespond with valid JSON only. No markdown, no explanation."
    raw = await generate(full_prompt, task_type, system_prompt, temperature=0.3)

    raw = raw.strip()
    # Strip markdown code fences
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to find JSON in the response
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end])
            except json.JSONDecodeError:
                pass
        # Try array
        start = raw.find("[")
        end = raw.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end])
            except json.JSONDecodeError:
                pass
        return {"error": "Failed to parse JSON", "raw": raw[:500]}


def generate_sync(prompt: str, task_type: str = "creative",
                  system_prompt: str = None) -> str:
    """Synchronous wrapper for generate."""
    _llm_stats["calls"] += 1
    try:
        return _call_claude(prompt, system_prompt)
    except Exception as e:
        _record_failure(task_type, e)
        return f"[LLM unavailable: {e}]"


async def check_health() -> dict:
    """Check if Claude CLI is available."""
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return {
                "status": "healthy",
                "provider": "claude-cli",
                "version": result.stdout.strip(),
                "models": ["sonnet"],
            }
        return {"status": "unavailable", "error": result.stderr.strip()}
    except Exception as e:
        return {"status": "unavailable", "error": str(e)}
