"""
Front Office - Ollama Client
Routes prompts to the right local LLM model.
qwen3:32b for GM decisions/trade evaluation (strategic reasoning)
qwen3:14b for flavor text/scouting reports/messages (creative, speed)
"""
import httpx
import json
import asyncio

OLLAMA_BASE = "http://localhost:11434"

# Model routing
MODELS = {
    "strategic": "qwen3:32b",   # GM decisions, trade eval, negotiation
    "creative": "qwen3:14b",    # scouting reports, messages, articles
    "batch": "qwen3:32b",       # offseason processing
}


async def generate(prompt: str, task_type: str = "creative",
                   system_prompt: str = None, temperature: float = 0.7,
                   max_tokens: int = 1024) -> str:
    """Send a prompt to Ollama and return the response text."""
    model = MODELS.get(task_type, MODELS["creative"])

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        }
    }
    if system_prompt:
        payload["system"] = system_prompt

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{OLLAMA_BASE}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "")
    except Exception as e:
        return f"[LLM unavailable: {e}]"


async def generate_json(prompt: str, task_type: str = "strategic",
                        system_prompt: str = None) -> dict:
    """Generate a structured JSON response from the LLM."""
    full_prompt = prompt + "\n\nRespond with valid JSON only. No markdown, no explanation."
    raw = await generate(full_prompt, task_type, system_prompt, temperature=0.3)

    # Try to extract JSON from response
    raw = raw.strip()
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
        return {"error": "Failed to parse JSON", "raw": raw}


def generate_sync(prompt: str, task_type: str = "creative",
                  system_prompt: str = None) -> str:
    """Synchronous wrapper for generate."""
    return asyncio.run(generate(prompt, task_type, system_prompt))


async def check_health() -> dict:
    """Check if Ollama is running and which models are available."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            return {
                "status": "healthy",
                "models": models,
                "has_strategic": any("32b" in m for m in models),
                "has_creative": any("14b" in m for m in models),
            }
    except Exception as e:
        return {"status": "unavailable", "error": str(e)}
