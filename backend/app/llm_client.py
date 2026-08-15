"""
Thin wrapper around the OpenAI API. Every other module calls the LLM
through the two helpers here, so there is exactly one place that touches
the SDK, one place that handles retries/parsing, and one place you'd
change if you swapped models.
"""
import json
import re
from functools import lru_cache

from openai import OpenAI

from app.config import settings


@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    return OpenAI(api_key=settings.require_api_key())


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def call_llm_text(system: str, user: str, max_tokens: int = 1500, temperature: float = 0.2) -> str:
    """Plain-text completion. Returns the response content."""
    client = get_client()
    resp = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        max_completion_tokens=max_tokens,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


def call_llm_json(system: str, user: str, max_tokens: int = 1500) -> dict:
    """
    Completion where we've instructed the model (in the system prompt) to
    return ONLY JSON. Uses OpenAI's JSON mode so this is reliable, but we
    still defensively strip code fences and fall back to a best-effort
    regex extraction, since hackathon demos shouldn't die on a stray
    sentence.
    """
    client = get_client()
    resp = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        max_completion_tokens=max_tokens,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    raw = resp.choices[0].message.content or ""
    cleaned = _strip_code_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"Model did not return parseable JSON:\n{raw}")
