import json

import pytest
from schemas.state import CouncilOutput
from worker.council.parser import neutral_output, parse_with_retry


def _valid_json(persona: str = "Contrarian") -> str:
    return json.dumps(
        {
            "persona": persona,
            "stance": "bullish",
            "rationale": "Strong fundamentals support a buy.",
            "confidence": 0.85,
            "citations": ["PE=28, below sector avg"],
        }
    )


@pytest.mark.asyncio
async def test_valid_json_returns_council_output():
    async def no_retry() -> str:
        raise AssertionError("retry should not be called on valid JSON")

    result = await parse_with_retry(_valid_json("Contrarian"), "Contrarian", no_retry)
    assert isinstance(result, CouncilOutput)
    assert result.stance == "bullish"
    assert result.persona == "Contrarian"


@pytest.mark.asyncio
async def test_invalid_json_triggers_retry():
    retried = False

    async def retry_call() -> str:
        nonlocal retried
        retried = True
        return _valid_json("Contrarian")

    result = await parse_with_retry("not json at all", "Contrarian", retry_call)
    assert retried is True
    assert result.stance == "bullish"


@pytest.mark.asyncio
async def test_double_failure_returns_neutral():
    async def retry_call() -> str:
        return "still not json"

    result = await parse_with_retry("not json", "Expansionist", retry_call)
    assert result.persona == "Expansionist"
    assert result.stance == "neutral"
    assert result.confidence == 0.0
    assert "parse failed" in result.rationale


@pytest.mark.asyncio
async def test_markdown_fenced_json_is_parsed():
    fenced = "```json\n" + _valid_json("Outsider") + "\n```"

    async def no_retry() -> str:
        raise AssertionError("retry should not be called")

    result = await parse_with_retry(fenced, "Outsider", no_retry)
    assert result.stance == "bullish"


@pytest.mark.asyncio
async def test_retry_exception_returns_neutral():
    async def failing_retry() -> str:
        raise RuntimeError("LLM unavailable")

    result = await parse_with_retry("bad json", "FirstPrinciples", failing_retry)
    assert result.stance == "neutral"
    assert result.confidence == 0.0


def test_neutral_output_has_correct_fields():
    out = neutral_output("FirstPrinciples")
    assert out.persona == "FirstPrinciples"
    assert out.stance == "neutral"
    assert out.confidence == 0.0
    assert "parse failed" in out.rationale


@pytest.mark.asyncio
async def test_non_dict_json_returns_neutral():
    """Valid JSON that is not an object should return neutral, not crash."""

    async def retry_call() -> str:
        return "still not a dict"

    result = await parse_with_retry("null", "Contrarian", retry_call)
    assert result.stance == "neutral"
    assert result.confidence == 0.0
