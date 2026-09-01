import json
import re

from anthropic import Anthropic
from fastapi import HTTPException

from app.config import settings

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if not settings.anthropic_api_key or settings.anthropic_api_key.startswith("sk-ant-REPLACE"):
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not configured. Add a real key to .env to use AI features.",
        )
    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


def complete(system: str, prompt: str, max_tokens: int = 1000) -> str:
    client = _get_client()
    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "max_tokens":
        raise HTTPException(
            status_code=502,
            detail=f"Claude's response was cut off at the {max_tokens}-token limit. Raise max_tokens for this call.",
        )
    return "".join(block.text for block in response.content if block.type == "text")


def complete_json(system: str, prompt: str, max_tokens: int = 1000) -> dict:
    text = complete(system, prompt, max_tokens=max_tokens)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise HTTPException(status_code=502, detail="Claude did not return valid JSON")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail=f"Claude returned malformed JSON: {exc}") from exc
