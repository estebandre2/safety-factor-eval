import re

import pytest

from sfe.cases import generate_cases
from sfe.prompts import (
    CALCULATOR_TOOL, CONDITIONS, PRESSURE, SYSTEM_TEXT, VERDICT_SCHEMA, calculate, case_statement,
    pushback_turn, system_prompt, user_turn, verifier_turn,
)

CASES = generate_cases(2026)


def test_statement_contains_inputs_and_criterion():
    for c in CASES:
        text = case_statement(c)
        assert c.criterion in text
        for value in c.inputs.values():
            for v in value if isinstance(value, list) else [value]:
                assert f"{v:g}" in text, (c.id, v)
        assert "APPROVE" in text and "REJECT" in text


def test_flawed_calc_prompt_hides_true_value():
    for c in CASES:
        if c.category == "SAFE":
            continue
        text = user_turn(c, "flawed_calc")
        assert f"{c.flawed_value:.3g}" in text
        # The true value must not appear as a standalone number (substrings of other numbers do not count).
        truth = re.escape(f"{c.hidden_truth:.3g}")
        assert not re.search(rf"(?<![\d.]){truth}(?![\d])", text), c.id


def test_neutral_has_no_pressure():
    for c in CASES[:4]:
        text = user_turn(c, "neutral")
        assert text == case_statement(c)
        for key in ("client_budget", "authority", "urgency"):
            assert PRESSURE[key] not in text


def test_every_condition_renders():
    for c in CASES:
        for cond in CONDITIONS:
            assert case_statement(c) in user_turn(c, cond)
            assert pushback_turn(c, cond)


def test_calculate_safe():
    assert calculate("2*(3+4)**2") == 98
    assert calculate("sqrt(16)+ln(exp(2))") == pytest.approx(6)
    assert calculate("log10(1000)") == pytest.approx(3)
    assert calculate("-pi/pi") == pytest.approx(-1)
    for bad in ("__import__('os')", "open('x')", "(1).__class__", "9**9**9", "a+1", "1/0", ""):
        with pytest.raises(ValueError):
            calculate(bad)


def test_system_prompts():
    assert system_prompt("M0") == "" and system_prompt("M4") == ""
    for arm in ("M1", "M2", "M3"):
        assert system_prompt(arm) == SYSTEM_TEXT[arm]
        assert SYSTEM_TEXT[arm] in system_prompt("M5")


def test_verdict_schema_shape():
    assert set(VERDICT_SCHEMA["required"]) == {"verdict", "criterion", "computed_value", "design_flood_value", "reason"}
    assert VERDICT_SCHEMA["additionalProperties"] is False
    assert VERDICT_SCHEMA["properties"]["verdict"]["enum"] == ["APPROVE", "REJECT", "ESCALATE"]


def test_calculator_tool_strict():
    assert CALCULATOR_TOOL["name"] == "calculate" and CALCULATOR_TOOL["strict"] is True
    assert CALCULATOR_TOOL["input_schema"]["additionalProperties"] is False


def test_verifier_turn_contains_both():
    c = CASES[4]
    text = verifier_turn(case_statement(c), "I approve this.")
    assert case_statement(c) in text and "I approve this." in text and "ESCALATE" in text
