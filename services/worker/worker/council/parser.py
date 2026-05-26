from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable

from schemas.state import CouncilOutput

logger = logging.getLogger(__name__)


def _parse(text: str, persona: str) -> CouncilOutput | None:
    """Attempt to parse LLM text into CouncilOutput. Returns None on any failure."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
        data.setdefault("persona", persona)
        return CouncilOutput.model_validate(data)
    except (json.JSONDecodeError, ValueError, KeyError):
        return None


def neutral_output(persona: str) -> CouncilOutput:
    """Return a neutral CouncilOutput used when all parse attempts fail."""
    return CouncilOutput(
        persona=persona,
        stance="neutral",
        rationale="parse failed after retry",
        confidence=0.0,
        citations=[],
    )


async def parse_with_retry(
    first_response: str,
    persona: str,
    retry_call: Callable[[], Awaitable[str]],
) -> CouncilOutput:
    """Parse first_response; on failure invoke retry_call once and parse again.

    Returns neutral_output if both attempts fail or if retry_call raises.
    """
    result = _parse(first_response, persona)
    if result is not None:
        return result

    logger.warning("Parse failed for persona %s, retrying LLM call", persona)
    try:
        retry_response = await retry_call()
        result = _parse(retry_response, persona)
    except Exception:
        logger.exception("Retry LLM call failed for persona %s", persona)
        result = None

    return result if result is not None else neutral_output(persona)
