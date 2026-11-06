"""Claude backend: one Message Batch per conversation round (50% batch pricing)."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from sfe.engine import Reply
from sfe.prompts import VERDICT_SCHEMA

PRICES: dict[str, tuple[float, float]] = {  # USD per 1M input / output tokens
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-opus-5-5": (4.0, 20.0),
}
BATCH_DISCOUNT = 0.5
EFFORT = "medium"
MAX_TOKENS = 8000
BATCH_LOG = Path("results/raw/batches.log")


def to_claude_params(request: dict, model: str) -> dict:
    """Messages API params. No sampling parameters, no prefill, no forced tool_choice (all rejected by these models)."""
    output_config: dict = {"effort": EFFORT}
    if request.get("structured"):
        output_config["format"] = {"type": "json_schema", "schema": request.get("schema") or VERDICT_SCHEMA}
    params: dict = {"model": model, "max_tokens": MAX_TOKENS, "messages": request["messages"], "output_config": output_config}
    if request.get("system"):
        params["system"] = request["system"]
    if request.get("tools"):
        params["tools"] = request["tools"]
    return params


def reply_from_message(message) -> Reply:
    blocks = [b.model_dump(exclude_none=True) for b in message.content]
    text = "".join(b.get("text", "") for b in blocks if b["type"] == "text")
    calls = [{"id": b["id"], "name": b["name"], "input": b["input"]} for b in blocks if b["type"] == "tool_use"]
    usage = {"input_tokens": int(message.usage.input_tokens), "output_tokens": int(message.usage.output_tokens)}
    return Reply(text=text, tool_calls=calls, stop_reason=str(message.stop_reason), usage=usage, raw_content=blocks)


def claude_cost(usage: dict[str, int], model: str, batch: bool = True) -> float:
    price_in, price_out = PRICES[model]
    cost = (usage.get("input_tokens", 0) * price_in + usage.get("output_tokens", 0) * price_out) / 1_000_000
    return cost * (BATCH_DISCOUNT if batch else 1.0)


def _error_reply() -> Reply:
    return Reply(text="", tool_calls=[], stop_reason="error", usage={"input_tokens": 0, "output_tokens": 0}, raw_content=[])


def run_claude_round(requests: dict[str, tuple[dict, str]], poll_seconds: int = 30) -> dict[str, Reply]:
    """Submit every request of one round as a single batch and wait for it. Keys are custom_ids."""
    import anthropic
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    client = anthropic.Anthropic()  # credentials from the environment or an `ant auth login` profile
    batch = client.messages.batches.create(requests=[
        Request(custom_id=cid, params=MessageCreateParamsNonStreaming(**to_claude_params(req, model)))
        for cid, (req, model) in requests.items()
    ])
    BATCH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with BATCH_LOG.open("a") as fh:
        fh.write(f"{datetime.now(timezone.utc).isoformat()} {batch.id} {len(requests)} requests\n")
    while client.messages.batches.retrieve(batch.id).processing_status != "ended":
        time.sleep(poll_seconds)

    replies = {cid: _error_reply() for cid in requests}
    for result in client.messages.batches.results(batch.id):
        if result.result.type == "succeeded":
            replies[result.custom_id] = reply_from_message(result.result.message)
    return replies
