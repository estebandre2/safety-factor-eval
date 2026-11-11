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


def test_ollama_thinking_model_gets_think_flag_budget_and_review_schema():
    import sfe.backends.ollama as ol
    from sfe.backends.ollama import run_ollama
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": '{"calculation": "CORRECT"}', "thinking": "hmm"},
                                         "done_reason": "stop", "prompt_eval_count": 10, "eval_count": 99})

    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://ollama")
    ol.THINKING_MODELS.add("think-model")
    reply = run_ollama(REQ, "think-model", client=http)
    assert seen["think"] is True and seen["options"]["num_predict"] >= 16000
    assert seen["format"] == REQ["schema"]
    assert reply.text == '{"calculation": "CORRECT"}' and reply.usage["output_tokens"] == 99


def test_qwen3_runs_in_non_thinking_mode():
    seen = {}

    def handler(request):
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": "ok"}, "done_reason": "stop"})

    from sfe.backends.ollama import run_ollama
    run_ollama(REQ, "qwen3:14b", client=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://o"))
    assert seen["think"] is False


def test_openrouter_error_body_with_200_becomes_runtime_error(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-test")
    from sfe.backends.deepseek import OPENROUTER_BASE_URL, run_openrouter
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"error": {"message": "x"}})),
                        base_url=OPENROUTER_BASE_URL)
    try:
        run_openrouter(REQ, "gpt-oss-120b", client=http)
        raised = None
    except RuntimeError as exc:
        raised = str(exc)
    assert raised and "unexpected response" in raised


def test_score_review_tolerates_non_numeric_reviewer_value():
    from pathlib import Path
    from sfe.cases import load_cases
    from sfe.review import score_review
    case = next(c for c in load_cases(Path("data/cases_phase1.jsonl")) if c.family == "overturning")
    out = score_review(case, {"numeric_error": True}, '{"calculation": "INCORRECT", "reviewer_value": "approx 2", "design_verdict": "REJECT"}')
    assert out["detected"] is True and out["value_correct"] is None


def test_gemini_empty_candidates_is_refusal(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g")
    from sfe.backends.gemini import GEMINI_MODEL, run_gemini
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"promptFeedback": {"blockReason": "OTHER"}})),
                        base_url="https://generativelanguage.googleapis.com")
    assert run_gemini(REQ, GEMINI_MODEL, client=http).stop_reason == "refusal"
