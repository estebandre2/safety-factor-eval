"""Gemini backend for the optional third-provider reviewer (Study II Phase 2, free tier). Raw HTTP; the key is
sent in the x-goog-api-key header, never in the URL."""
from __future__ import annotations

import os
import time

import httpx

from sfe.engine import Reply

BASE_URL = "https://generativelanguage.googleapis.com"
GEMINI_MODEL = "gemini-3-flash-preview"  # the free-tier model that answered in the 2026-11-10 key test
RETRIES = 4
FINISH = {"STOP": "end_turn", "MAX_TOKENS": "max_tokens", "SAFETY": "refusal", "RECITATION": "refusal"}


def run_gemini(request: dict, model: str = GEMINI_MODEL, client: httpx.Client | None = None) -> Reply:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set (add it to .env)")
    contents = [{"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
                for m in request["messages"] if isinstance(m["content"], str)]
    body: dict = {"contents": contents}
    if request.get("system"):
        body["systemInstruction"] = {"parts": [{"text": request["system"]}]}
    if request.get("structured"):
        body["generationConfig"] = {"responseMimeType": "application/json"}
    http = client or httpx.Client(base_url=BASE_URL, timeout=600)
    for attempt in range(RETRIES):
        response = http.post(f"/v1beta/models/{model}:generateContent", json=body, headers={"x-goog-api-key": key})
        if response.status_code in (429, 500, 503) and attempt < RETRIES - 1:
            time.sleep(2 ** attempt * 15)  # free tier: back off on rate limits and "high demand"
            continue
        break
    response.raise_for_status()
    data = response.json()
    cand = (data.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []) if not p.get("thought"))
    usage = data.get("usageMetadata", {})
    out = int(usage.get("candidatesTokenCount", 0)) + int(usage.get("thoughtsTokenCount", 0))
    return Reply(text=text.strip(), tool_calls=[], stop_reason=FINISH.get(cand.get("finishReason"), "end_turn"),
                 usage={"input_tokens": int(usage.get("promptTokenCount", 0)), "output_tokens": out},
                 raw_content=[{"type": "text", "text": text.strip()}] if text else [])
