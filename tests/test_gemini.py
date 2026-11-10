import json

import httpx

from sfe.backends.gemini import GEMINI_MODEL, run_gemini

REQ = {"system": "", "messages": [{"role": "user", "content": "review this"}], "tools": [], "structured": True,
       "schema": {"type": "object", "properties": {"calculation": {"type": "string"}}, "required": ["calculation"]}}


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://generativelanguage.googleapis.com")


def test_request_shape_key_in_header_and_reply(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g-test")
    seen = {}

    def handler(request):
        seen["key"] = request.headers.get("x-goog-api-key")
        seen["path"] = request.url.path
        seen["query"] = str(request.url.query)
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={
            "candidates": [{"content": {"parts": [{"text": '{"calculation": "INCORRECT"}'}]}, "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 30, "candidatesTokenCount": 10, "thoughtsTokenCount": 50}})

    reply = run_gemini(REQ, GEMINI_MODEL, client=client(handler))
    assert seen["key"] == "g-test" and "key=" not in seen["query"]
    assert seen["path"].endswith(f"/models/{GEMINI_MODEL}:generateContent")
    assert seen["contents"][0] == {"role": "user", "parts": [{"text": "review this"}]}
    assert seen["generationConfig"]["responseMimeType"] == "application/json"
    assert reply.text == '{"calculation": "INCORRECT"}' and reply.stop_reason == "end_turn"
    assert reply.usage == {"input_tokens": 30, "output_tokens": 60}


def test_rate_limit_is_retried_then_error(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g-test")
    monkeypatch.setattr("sfe.backends.gemini.time.sleep", lambda s: None)
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(429, json={"error": {"status": "RESOURCE_EXHAUSTED"}})

    try:
        run_gemini(REQ, GEMINI_MODEL, client=client(handler))
        raised = False
    except httpx.HTTPStatusError:
        raised = True
    assert raised and calls["n"] >= 2
