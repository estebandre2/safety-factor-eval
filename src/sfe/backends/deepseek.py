"""DeepSeek backend (OpenAI-compatible Chat Completions over raw HTTP). Synchronous; the runner parallelizes."""
from __future__ import annotations

import json
import os
import time

import httpx

from sfe.engine import Reply
from sfe.prompts import VERDICT_SCHEMA

BASE_URL = "https://api.deepseek.com"
REASONING_EFFORT = "high"  # DeepSeek maps "medium" to "high"; thinking stays on, as with the Claude models
MAX_TOKENS = 32000  # reasoning tokens count toward completion tokens
RETRIES = 3
JSON_HINT = (
    "Respond with one json object only, with exactly these keys: "
    '{"verdict": "APPROVE" | "REJECT" | "ESCALATE", "criterion": "<criterion>", '
    '"computed_value": <number or null>, "design_flood_value": <number or null>, "reason": "<short reason>"}'
)
FINISH = {"stop": "end_turn", "tool_calls": "tool_use", "length": "max_tokens", "content_filter": "refusal",
          "insufficient_system_resource": "error", "aborted": "error"}


def to_openai_messages(system: str, messages: list[dict]) -> list[dict]:
    out: list[dict] = [{"role": "system", "content": system}] if system else []
    for msg in messages:
        content = msg["content"]
        if isinstance(content, str):
            out.append({"role": msg["role"], "content": content})
            continue
        if msg["role"] == "assistant":
            text = "".join(b.get("text", "") for b in content if b["type"] == "text")
            entry: dict = {"role": "assistant", "content": text}
            calls = [b for b in content if b["type"] == "tool_use"]
            if calls:
                entry["tool_calls"] = [{"id": c["id"], "type": "function",
                                        "function": {"name": c["name"], "arguments": json.dumps(c["input"])}} for c in calls]
            out.append(entry)
        else:
            for block in content:
                if block["type"] == "tool_result":
                    out.append({"role": "tool", "tool_call_id": block["tool_use_id"], "content": block["content"]})
                elif block["type"] == "text":
                    out.append({"role": "user", "content": block["text"]})
    return out


def _arguments(raw: str) -> dict:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def run_deepseek(request: dict, model: str, client: httpx.Client | None = None) -> Reply:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set (add it to .env)")
    system = request.get("system", "")
    if request.get("structured"):
        system = f"{system}\n\n{JSON_HINT}".strip()
    body: dict = {"model": model, "messages": to_openai_messages(system, request["messages"]),
                  "reasoning_effort": REASONING_EFFORT, "max_tokens": MAX_TOKENS, "stream": False}
    if request.get("tools"):
        body["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                           "parameters": t["input_schema"]}} for t in request["tools"]]
    if request.get("structured"):
        body["response_format"] = {"type": "json_object"}

    http = client or httpx.Client(base_url=BASE_URL, timeout=900)
    headers = {"Authorization": f"Bearer {key}"}
    for attempt in range(RETRIES):
        response = http.post("/chat/completions", json=body, headers=headers)
        if response.status_code in (429, 500, 502, 503) and attempt < RETRIES - 1:
            time.sleep(2 ** attempt * 5)
            continue
        break
    response.raise_for_status()
    data = response.json()
    choice = data["choices"][0]
    message = choice.get("message", {})
    text = (message.get("content") or "").strip()
    calls = [{"id": c["id"], "name": c["function"]["name"], "input": _arguments(c["function"].get("arguments"))}
             for c in message.get("tool_calls") or []]
    raw = [{"type": "text", "text": text}] if text else []
    raw += [{"type": "tool_use", **c} for c in calls]
    usage = data.get("usage", {})
    return Reply(text=text, tool_calls=calls, stop_reason=FINISH.get(choice.get("finish_reason"), "end_turn"),
                 usage={"input_tokens": int(usage.get("prompt_tokens", 0)), "output_tokens": int(usage.get("completion_tokens", 0))},
                 raw_content=raw)


def deepseek_balance(client: httpx.Client | None = None) -> float:
    """Remaining USD balance, used to measure real spend before and after a run."""
    http = client or httpx.Client(base_url=BASE_URL, timeout=60)
    data = http.get("/user/balance", headers={"Authorization": f"Bearer {os.environ['DEEPSEEK_API_KEY']}"}).json()
    return sum(float(b["total_balance"]) for b in data.get("balance_infos", []) if b.get("currency") == "USD")
