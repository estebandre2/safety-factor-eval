import json
import os

import httpx
import pytest

from sfe.backends.claude import PRICES, claude_cost, reply_from_message, to_claude_params
from sfe.backends.ollama import ToolsUnsupported, run_ollama, to_ollama_messages
from sfe.prompts import CALCULATOR_TOOL, VERDICT_SCHEMA

REQ = {"system": "be careful", "messages": [{"role": "user", "content": "hi"}], "tools": [], "structured": False}


def test_to_claude_params_has_no_sampling_or_forced_tool():
    params = to_claude_params({**REQ, "tools": [CALCULATOR_TOOL]}, "claude-sonnet-5-5")
    for key in ("temperature", "top_p", "top_k"):
        assert key not in params
    assert params.get("tool_choice", {"type": "auto"}) == {"type": "auto"}
    assert params["output_config"]["effort"] == "medium"
    assert params["model"] == "claude-sonnet-5-5" and params["system"] == "be careful"
    assert params["tools"] == [CALCULATOR_TOOL]
    assert "system" not in to_claude_params({**REQ, "system": ""}, "claude-haiku-5-5")


def test_structured_sets_json_schema_format():
    params = to_claude_params({**REQ, "structured": True}, "claude-haiku-5-5")
    assert params["output_config"]["format"] == {"type": "json_schema", "schema": VERDICT_SCHEMA}


def test_claude_cost():
    usage = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
    assert claude_cost(usage, "claude-sonnet-5-5") == pytest.approx(6.0)
    assert claude_cost(usage, "claude-sonnet-5-5", batch=False) == pytest.approx(12.0)
    assert set(PRICES) == {"claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"}


class Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def model_dump(self, exclude_none=True):
        return {k: v for k, v in self.__dict__.items() if v is not None or not exclude_none}


class Msg:
    def __init__(self, content, stop_reason, usage):
        self.content, self.stop_reason, self.usage = content, stop_reason, usage


def test_reply_from_message_maps_text_tools_and_thinking():
    msg = Msg(
        [Block(type="thinking", thinking="", signature="sig"), Block(type="text", text="Let me compute."),
         Block(type="tool_use", id="tu1", name="calculate", input={"expression": "1+1"})],
        "tool_use", Block(input_tokens=12, output_tokens=7),
    )
    reply = reply_from_message(msg)
    assert reply.text == "Let me compute." and reply.stop_reason == "tool_use"
    assert reply.tool_calls == [{"id": "tu1", "name": "calculate", "input": {"expression": "1+1"}}]
    assert reply.raw_content[0] == {"type": "thinking", "thinking": "", "signature": "sig"}
    assert reply.usage == {"input_tokens": 12, "output_tokens": 7}


def _mock(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://ollama")


def test_ollama_reply_parsing():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        body = {"message": {"role": "assistant", "content": "",
                            "tool_calls": [{"function": {"name": "calculate", "arguments": {"expression": "2*3"}}}]},
                "done_reason": "stop", "prompt_eval_count": 30, "eval_count": 9}
        return httpx.Response(200, json=body)

    reply = run_ollama({**REQ, "tools": [CALCULATOR_TOOL], "structured": True}, "qwen3:4b", client=_mock(handler))
    assert seen["model"] == "qwen3:4b" and seen["stream"] is False and seen["format"] == VERDICT_SCHEMA
    assert seen["messages"][0] == {"role": "system", "content": "be careful"}
    assert seen["tools"][0]["function"]["name"] == "calculate"
    assert reply.tool_calls[0]["name"] == "calculate" and reply.tool_calls[0]["input"] == {"expression": "2*3"}
    assert reply.stop_reason == "tool_use" and reply.usage == {"input_tokens": 30, "output_tokens": 9}


def test_ollama_length_maps_to_max_tokens():
    def handler(request):
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "cut"}, "done_reason": "length",
                                         "prompt_eval_count": 1, "eval_count": 1})

    assert run_ollama(REQ, "m", client=_mock(handler)).stop_reason == "max_tokens"


def test_ollama_tools_unsupported_marks_trial():
    def handler(request):
        return httpx.Response(400, json={"error": "registry.ollama.ai/library/gemma4:e4b does not support tools"})

    with pytest.raises(ToolsUnsupported):
        run_ollama({**REQ, "tools": [CALCULATOR_TOOL]}, "gemma4:e4b", client=_mock(handler))


def test_to_ollama_messages_converts_tool_blocks():
    messages = [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": [{"type": "thinking", "thinking": "", "signature": "s"}, {"type": "text", "text": "ok"},
                                          {"type": "tool_use", "id": "c0", "name": "calculate", "input": {"expression": "1"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c0", "content": "1"}]},
    ]
    out = to_ollama_messages("", messages)
    assert out[1] == {"role": "assistant", "content": "ok",
                      "tool_calls": [{"function": {"name": "calculate", "arguments": {"expression": "1"}}}]}
    assert out[2] == {"role": "tool", "content": "1", "tool_name": "calculate"}


@pytest.mark.skipif(os.environ.get("SFE_LIVE") != "1", reason="live calls are opt-in")
def test_live_smoke():
    from sfe.backends.claude import run_claude_round
    replies = run_claude_round({"smoke": ({**REQ, "messages": [{"role": "user", "content": "Reply with OK."}]}, "claude-haiku-5-5")}, poll_seconds=10)
    assert replies["smoke"].stop_reason in ("end_turn", "refusal")
    assert run_ollama({**REQ, "messages": [{"role": "user", "content": "Reply with OK."}]}, "qwen3:4b-instruct-2507-q4_K_M").text
