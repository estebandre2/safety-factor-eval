import json

import httpx

from sfe.backends.deepseek import OPENROUTER_BASE_URL, OPENROUTER_MODELS, run_openrouter
from sfe.run import sync_backend

REQ = {"system": "", "messages": [{"role": "user", "content": "check"}], "tools": [], "structured": True,
       "schema": {"type": "object", "properties": {"calculation": {"type": "string"}}, "required": ["calculation"]}}


def test_openrouter_request_shape(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    seen = {}

    def handler(request):
        seen["auth"] = request.headers["authorization"]
        seen["url"] = str(request.url)
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"calculation": "CORRECT"}'},
                                                      "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 12, "completion_tokens": 34}})

    http = httpx.Client(transport=httpx.MockTransport(handler), base_url=OPENROUTER_BASE_URL)
    reply = run_openrouter(REQ, "gpt-oss-120b", client=http)
    assert seen["auth"] == "Bearer or-test"
    assert seen["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert seen["model"] == OPENROUTER_MODELS["gpt-oss-120b"] == "openai/gpt-oss-120b"
    assert seen["reasoning"] == {"effort": "high"} and "reasoning_effort" not in seen
    assert seen["provider"] == {"order": ["Groq"], "allow_fallbacks": False, "require_parameters": True}
    assert seen["response_format"] == {"type": "json_object"}
    assert "json" in seen["messages"][0]["content"].lower()
    assert reply.text == '{"calculation": "CORRECT"}' and reply.usage == {"input_tokens": 12, "output_tokens": 34}


def test_openrouter_needs_its_own_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-other")
    try:
        run_openrouter(REQ, "gpt-oss-120b")
        raised = False
    except RuntimeError as exc:
        raised = "OPENROUTER_API_KEY" in str(exc)
    assert raised


def test_sync_backend_routes_by_model():
    from sfe.backends.deepseek import run_deepseek
    from sfe.backends.gemini import run_gemini
    from sfe.backends.ollama import run_ollama
    assert sync_backend("deepseek-flash") is run_deepseek
    assert sync_backend("gemini-3-flash-preview") is run_gemini
    assert sync_backend("gpt-oss-120b") is run_openrouter
    assert sync_backend("qwen3:8b") is run_ollama
