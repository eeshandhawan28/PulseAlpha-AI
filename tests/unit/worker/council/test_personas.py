from worker.council.personas import PERSONA_NAMES, PERSONAS, build_reconciliation_prompt


def test_all_five_personas_in_registry():
    assert set(PERSONA_NAMES) == {
        "Contrarian", "FirstPrinciples", "Expansionist", "Outsider", "Synthesizer"
    }
    assert set(PERSONAS.keys()) == set(PERSONA_NAMES)


def test_each_persona_prompt_is_nonempty_string():
    for name, prompt in PERSONAS.items():
        assert isinstance(prompt, str), f"{name} prompt is not a string"
        assert len(prompt) > 100, f"{name} prompt is too short"


def test_each_persona_prompt_contains_json_instruction():
    for name, prompt in PERSONAS.items():
        assert "JSON" in prompt, f"{name} prompt missing JSON instruction"
        assert "stance" in prompt, f"{name} prompt missing stance field"
        assert "rationale" in prompt, f"{name} prompt missing rationale field"


def test_reconciliation_prompt_contains_majority_and_rationale():
    prompt = build_reconciliation_prompt(
        "Contrarian", "bullish", "Strong FII inflows support the bullish view."
    )
    assert "bullish" in prompt
    assert "Strong FII inflows" in prompt
    assert "Contrarian" in prompt


def test_reconciliation_prompt_is_nonempty():
    prompt = build_reconciliation_prompt("Outsider", "bearish", "Divergence is high.")
    assert len(prompt) > 50
