"""
Ollama API client for running analysis through local LLMs.
"""

from __future__ import annotations

import json
import re
import time
from typing import Optional, Tuple

import requests


OLLAMA_BASE_URL = "http://localhost:11434"


def check_ollama_available() -> bool:
    """Check if Ollama is running and accessible."""
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        return resp.status_code == 200
    except requests.ConnectionError:
        return False


def list_models() -> list[str]:
    """List available Ollama models."""
    resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
    resp.raise_for_status()
    return [m["name"] for m in resp.json().get("models", [])]


def run_analysis(model: str, prompt: str, timeout: int = 1800) -> dict:
    """
    Send a prompt to Ollama and parse the JSON response.

    Returns a dict with:
        - "response": parsed JSON analysis (or None if parsing failed)
        - "raw": raw text response from the model
        - "duration_seconds": how long the model took
        - "parse_error": error message if JSON parsing failed
        - "error": set if there was a network/timeout error
    """
    start = time.time()

    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 4096,
                },
            },
            timeout=timeout,
        )
        resp.raise_for_status()
    except requests.exceptions.ReadTimeout:
        duration = time.time() - start
        return {
            "response": None,
            "raw": "",
            "duration_seconds": round(duration, 1),
            "parse_error": f"Request timed out after {timeout}s",
            "error": "timeout",
        }
    except requests.exceptions.RequestException as e:
        duration = time.time() - start
        return {
            "response": None,
            "raw": "",
            "duration_seconds": round(duration, 1),
            "parse_error": str(e),
            "error": "request_failed",
        }

    duration = time.time() - start
    raw_text = resp.json().get("response", "")

    # Try to parse JSON from the response
    parsed, error = _extract_json(raw_text)

    return {
        "response": parsed,
        "raw": raw_text,
        "duration_seconds": round(duration, 1),
        "parse_error": error,
    }


def _extract_json(text: str) -> Tuple[Optional[dict], Optional[str]]:
    """
    Extract JSON from LLM response text.
    Handles cases where the model wraps JSON in markdown code fences or adds commentary.
    """
    # Try direct parse first
    try:
        return json.loads(text.strip()), None
    except json.JSONDecodeError:
        pass

    # Try extracting from code fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip()), None
        except json.JSONDecodeError:
            pass

    # Try finding JSON object boundaries
    brace_start = text.find("{")
    if brace_start != -1:
        # Find the matching closing brace
        depth = 0
        for i in range(brace_start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[brace_start : i + 1]), None
                    except json.JSONDecodeError:
                        break

    return None, f"Could not parse JSON from response (length={len(text)})"
