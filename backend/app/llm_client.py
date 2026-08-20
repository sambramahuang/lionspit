"""
Thin wrapper around the OpenAI API. Every other module calls the LLM
through the helpers here, so there is exactly one place that touches
the SDK, one place that handles retries/parsing, and one place you'd
change if you swapped models.
"""
import base64
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


def transcribe_image(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """OCR fallback for an image-only page (a scanned document with no text
    layer) via the same vision-capable chat model everything else already
    uses -- no Tesseract/poppler binary needed, which matters because
    Vercel's serverless Python runtime can't apt-get one in. See
    ingestion.extract_text's PDF branch for the only caller: it renders a
    text-less page to an image (PyMuPDF, also binary-free) and hands it
    here as a last resort, not on every PDF."""
    client = get_client()
    b64 = base64.b64encode(image_bytes).decode("ascii")
    resp = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        max_completion_tokens=1500,
        temperature=0.0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You transcribe scanned legal documents. Read the image and "
                    "output every piece of text visible on the page -- body text, "
                    "signature blocks, printed and handwritten names, dates, "
                    "stamps -- in reading order, plain text only. If something is "
                    "illegible, write [illegible] in its place rather than "
                    "guessing. Do not add commentary, headers, or markdown."
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{b64}"},
                    }
                ],
            },
        ],
    )
    return resp.choices[0].message.content or ""


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Batch embedding call -- one request for N texts is both cheaper and
    faster than N separate calls. Order of the returned vectors matches
    the order of the input texts (OpenAI's API guarantees this via the
    `index` field, which we sort on defensively)."""
    if not texts:
        return []
    client = get_client()
    resp = client.embeddings.create(model=settings.OPENAI_EMBEDDING_MODEL, input=texts)
    return [d.embedding for d in sorted(resp.data, key=lambda d: d.index)]


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]


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
