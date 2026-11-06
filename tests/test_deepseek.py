import json

import httpx
import pytest

from sfe.backends.deepseek import JSON_HINT, run_deepseek, to_openai_messages
from sfe.prompts import CALCULATOR_TOOL

REQ = {"system": "be careful", "messages": [{"role": "user", "content": "hi"}], "tools": [], "structured": False}


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.deepseek.com")


def ok(message, finish="stop", usage=(40, 20)):
    return httpx.Response(200, json={"choices": [{"message": message, "finish_reason": finish}],
                                     "usage": {"prompt_tokens": usage[0], "completion_tokens": usage[1]}})


def test_request_shape_and_text_reply(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["authorization"]
        seen["path"] = request.url.path
        seen.update(json.loads(request.content))
        return ok({"role": "assistant", "content": "REJECT", "reasoning_content": "thinking..."})

    reply = run_deepseek({**REQ, "tools": [CALCULATOR_TOOL]}, "deepseek-v4-pro", client=client(handler))
    assert seen["auth"] == "Bearer sk-test" and seen["path"] == "/chat/completions"
    assert seen["model"] == "deepseek-v4-pro" and seen["reasoning_effort"] == "high"
    assert "temperature" not in seen and "tool_choice" not in seen
    assert seen["messages"][0] == {"role": "system", "content": "be careful"}
    assert seen["tools"][0]["function"]["name"] == "calculate"
    assert reply.text == "REJECT" and reply.stop_reason == "end_turn"
    assert reply.usage == {"input_tokens": 40, "output_tokens": 20}


def test_tool_calls_parsed_and_bad_arguments_tolerated(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    calls = [{"id": "c1", "type": "function", "function": {"name": "calculate", "arguments": '{"expression": "2*3"}'}},
             {"id": "c2", "type": "function", "function": {"name": "calculate", "arguments": "{not json"}}]
    reply = run_deepseek(REQ, "deepseek-flash", client=client(lambda r: ok({"role": "assistant", "content": None, "tool_calls": calls}, "tool_calls")))
    assert reply.stop_reason == "tool_use"
    assert reply.tool_calls[0] == {"id": "c1", "name": "calculate", "input": {"expression": "2*3"}}
    assert reply.tool_calls[1]["input"] == {}


@pytest.mark.parametrize("finish,expected", [("length", "max_tokens"), ("content_filter", "refusal"),
                                              ("insufficient_system_resource", "error"), ("aborted", "error")])
def test_finish_reason_mapping(monkeypatch, finish, expected):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    reply = run_deepseek(REQ, "deepseek-flash", client=client(lambda r: ok({"role": "assistant", "content": "x"}, finish)))
    assert reply.stop_reason == expected


def test_structured_uses_json_mode_with_hint(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return ok({"role": "assistant", "content": '{"verdict": "REJECT", "criterion": "x", "computed_value": 1.2, "reason": "r"}'})

    run_deepseek({**REQ, "structured": True}, "deepseek-flash", client=client(handler))
    assert seen["response_format"] == {"type": "json_object"}
    assert JSON_HINT in seen["messages"][0]["content"] and "json" in JSON_HINT.lower()


def test_blank_json_content_is_empty_text(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    reply = run_deepseek({**REQ, "structured": True}, "deepseek-flash", client=client(lambda r: ok({"role": "assistant", "content": "   "})))
    assert reply.text == ""


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        run_deepseek(REQ, "deepseek-flash", client=client(lambda r: ok({"content": "x"})))


def test_to_openai_messages_tool_round_trip():
    messages = [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": [{"type": "text", "text": "computing"},
                                          {"type": "tool_use", "id": "c1", "name": "calculate", "input": {"expression": "1+1"}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "2"}]},
    ]
    out = to_openai_messages("", messages)
    assert out[1]["tool_calls"][0] == {"id": "c1", "type": "function",
                                       "function": {"name": "calculate", "arguments": '{"expression": "1+1"}'}}
    assert out[2] == {"role": "tool", "tool_call_id": "c1", "content": "2"}
