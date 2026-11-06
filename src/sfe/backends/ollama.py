"""Local models through the Ollama REST API (synchronous)."""
from __future__ import annotations

import httpx

from sfe.engine import Reply
from sfe.prompts import VERDICT_SCHEMA

DEFAULT_URL = "http://localhost:11434"


class ToolsUnsupported(Exception):
    """The local model's template does not accept tools."""


def to_ollama_messages(system: str, messages: list[dict]) -> list[dict]:
    out: list[dict] = [{"role": "system", "content": system}] if system else []
    tool_names: dict[str, str] = {}
    for msg in messages:
        content = msg["content"]
        if isinstance(content, str):
            out.append({"role": msg["role"], "content": content})
            continue
        if msg["role"] == "assistant":
            text = "".join(b.get("text", "") for b in content if b["type"] == "text")
            calls = [b for b in content if b["type"] == "tool_use"]
            entry: dict = {"role": "assistant", "content": text}
            if calls:
                entry["tool_calls"] = [{"function": {"name": c["name"], "arguments": c["input"]}} for c in calls]
                tool_names.update({c["id"]: c["name"] for c in calls})
            out.append(entry)
        else:
            for block in content:
                if block["type"] == "tool_result":
                    out.append({"role": "tool", "content": block["content"],
                                "tool_name": tool_names.get(block["tool_use_id"], "calculate")})
                elif block["type"] == "text":
                    out.append({"role": "user", "content": block["text"]})
    return out


def run_ollama(request: dict, model: str, base_url: str = DEFAULT_URL, client: httpx.Client | None = None) -> Reply:
    body: dict = {"model": model, "stream": False, "messages": to_ollama_messages(request.get("system", ""), request["messages"])}
    if request.get("tools"):
        body["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                           "parameters": t["input_schema"]}} for t in request["tools"]]
    if request.get("structured"):
        body["format"] = VERDICT_SCHEMA
    http = client or httpx.Client(base_url=base_url, timeout=600)
    response = http.post("/api/chat", json=body)
    if response.status_code == 400 and "tool" in response.text.lower():
        raise ToolsUnsupported(response.text)
    response.raise_for_status()
    data = response.json()
    message = data.get("message", {})
    calls = [{"id": f"call_{i}", "name": c["function"]["name"], "input": c["function"].get("arguments", {})}
             for i, c in enumerate(message.get("tool_calls") or [])]
    raw = [{"type": "text", "text": message.get("content", "")}] if message.get("content") else []
    raw += [{"type": "tool_use", **c} for c in calls]
    stop = "tool_use" if calls else ("max_tokens" if data.get("done_reason") == "length" else "end_turn")
    usage = {"input_tokens": int(data.get("prompt_eval_count", 0)), "output_tokens": int(data.get("eval_count", 0))}
    return Reply(text=message.get("content", ""), tool_calls=calls, stop_reason=stop, usage=usage, raw_content=raw)
