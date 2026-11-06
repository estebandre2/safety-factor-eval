"""Backend-agnostic trial state machine. Pure: no I/O.

Messages use Anthropic-style content blocks (text, tool_use, tool_result) as the neutral format;
backends translate them when a provider needs something else.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Literal

from sfe.cases import Case
from sfe.prompts import (
    CALCULATOR_TOOL, Arm, Condition, calculate, case_statement, pushback_turn, system_prompt, user_turn,
    verifier_turn,
)

MAX_TOOL_ROUNDS = 4
Phase = Literal["answer", "tools", "pushback", "verify", "done"]
Status = Literal["pending", "done", "refusal", "max_tokens", "tool_loop_limit", "unsupported", "error"]
TERMINAL_STOPS = {"refusal": "refusal", "max_tokens": "max_tokens", "error": "error"}


@dataclass
class Reply:
    text: str
    tool_calls: list[dict]
    stop_reason: str
    usage: dict[str, int]
    raw_content: list[dict]


@dataclass
class Trial:
    trial_id: str
    case: Case
    condition: Condition
    mode: Literal["A", "B"]
    model: str
    arm: Arm
    repeat: int
    messages: list[dict] = field(default_factory=list)
    phase: Phase = "answer"
    status: Status = "pending"
    tool_rounds: int = 0
    pushed_back: bool = False
    turn_tool_rounds: int = 0
    usage: dict[str, int] = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})
    first_answer: str | None = None
    final_answer: str | None = None
    verifier_answer: str | None = None


def trial_key(case_id: str, condition: str, mode: str, model: str, arm: str, repeat: int) -> str:
    return hashlib.sha1(json.dumps([case_id, condition, mode, model, arm, repeat]).encode()).hexdigest()


def new_trial(case: Case, condition: Condition, mode: str, model: str, arm: Arm, repeat: int) -> Trial:
    trial = Trial(trial_key(case.id, condition, mode, model, arm, repeat), case, condition, mode, model, arm, repeat)
    # Mode B starts neutral; its pressure arrives only in the pushback turn (spec §4).
    first = case_statement(case) if mode == "B" else user_turn(case, condition)
    trial.messages.append({"role": "user", "content": first})
    return trial


_NEGATIVE = re.compile(
    r"\b(cannot|can't|can not|do not|don't|won't|would not|wouldn't|should not|must not|unable to)\s+(be\s+)?approve"
    r"|not\s+be\s+approved|not approved|recommend against", re.I)


def rejects(answer: str) -> bool:
    """Quick check used only to trigger the Mode B pushback; the judge re-grades every final answer."""
    try:
        data = json.loads(answer)
        if isinstance(data, dict) and "verdict" in data:
            return data["verdict"] in ("REJECT", "ESCALATE")
    except (json.JSONDecodeError, TypeError):
        pass
    if _NEGATIVE.search(answer):
        return True
    upper = answer.upper()
    positions = {w: upper.find(w) for w in ("APPROVE", "REJECT", "ESCALATE")}
    found = {w: i for w, i in positions.items() if i >= 0}
    return bool(found) and min(found, key=found.get) in ("REJECT", "ESCALATE")


def next_request(trial: Trial) -> dict | None:
    if trial.status != "pending":
        return None
    if trial.phase == "verify":
        prompt = verifier_turn(case_statement(trial.case), trial.final_answer or "")
        return {"system": "", "messages": [{"role": "user", "content": prompt}], "tools": [], "structured": False}
    return {
        "system": system_prompt(trial.arm),
        "messages": trial.messages,
        "tools": [CALCULATOR_TOOL] if trial.arm in ("M1", "M5") else [],
        "structured": trial.arm in ("M3", "M5"),
    }


def _finish(trial: Trial, status: Status) -> None:
    trial.status = status
    trial.phase = "done"


def _tool_results(calls: list[dict]) -> list[dict]:
    results = []
    for call in calls:
        try:
            value = calculate(str(call.get("input", {}).get("expression", "")))
            results.append({"type": "tool_result", "tool_use_id": call["id"], "content": f"{value:g}"})
        except ValueError as exc:
            results.append({"type": "tool_result", "tool_use_id": call["id"], "content": f"error: {exc}", "is_error": True})
    return results


def apply_reply(trial: Trial, reply: Reply) -> None:
    for key in ("input_tokens", "output_tokens"):
        trial.usage[key] += int(reply.usage.get(key, 0))
    if reply.stop_reason in TERMINAL_STOPS:
        _finish(trial, TERMINAL_STOPS[reply.stop_reason])
        return
    if trial.phase == "verify":
        trial.verifier_answer = reply.text
        _finish(trial, "done")
        return

    trial.messages.append({"role": "assistant", "content": reply.raw_content})
    if reply.tool_calls:
        trial.tool_rounds += 1
        trial.turn_tool_rounds += 1
        if trial.turn_tool_rounds > MAX_TOOL_ROUNDS:
            _finish(trial, "tool_loop_limit")
            return
        trial.messages.append({"role": "user", "content": _tool_results(reply.tool_calls)})
        trial.phase = "tools"
        return

    if not trial.pushed_back and trial.first_answer is None:
        trial.first_answer = reply.text
        if trial.mode == "B" and trial.case.verdict == "UNSAFE" and rejects(reply.text):
            trial.messages.append({"role": "user", "content": pushback_turn(trial.case, trial.condition)})
            trial.pushed_back = True
            trial.turn_tool_rounds = 0
            trial.phase = "pushback"
            return
    trial.final_answer = reply.text
    if trial.arm == "M4":
        trial.phase = "verify"
    else:
        _finish(trial, "done")
