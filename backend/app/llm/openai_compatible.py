"""OpenAI-compatible chat API over ``httpx`` (Groq and similar hosted providers). Task B1-A2-02, D-008.

POST ``{base_url}/chat/completions`` with temperature 0 and JSON mode. The API key is sent only in
the ``Authorization`` header; it never appears in logs or in error messages.
"""
from __future__ import annotations

import time

import httpx

from app.llm.gateway import DEFAULT_TIMEOUT_S, LLMClient, LLMError, LLMResponse, LLMTimeout, extract_json


class OpenAICompatibleClient(LLMClient):
    def __init__(self, *, base_url: str, api_key: str, model: str, timeout_s: float = DEFAULT_TIMEOUT_S,
                 provider: str = "openai_compatible", transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.provider = provider
        self.model = model
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._key = api_key or ""
        self._timeout = timeout_s
        self._transport = transport  # tests pass an httpx.MockTransport; no network in tests

    @property
    def ready(self) -> bool:
        return bool(self._key and self.model)

    def __repr__(self) -> str:  # never show the key
        return f"OpenAICompatibleClient(provider={self.provider!r}, model={self.model!r})"

    async def complete_json(self, system: str, user: str) -> LLMResponse:
        if not self._key:
            raise LLMError("LLM_API_KEY is not set")
        body = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                reply = await client.post(self._url, json=body, headers={"Authorization": f"Bearer {self._key}"})
        except httpx.TimeoutException:
            raise LLMTimeout() from None
        except httpx.HTTPError as exc:
            raise LLMError(f"cannot reach the language model ({exc.__class__.__name__})", transient=True) from None
        latency = round((time.perf_counter() - started) * 1000)
        if reply.status_code >= 400:
            transient = reply.status_code == 429 or reply.status_code >= 500
            raise LLMError(f"language model returned HTTP {reply.status_code}", transient=transient)
        try:
            payload = reply.json()
            content = payload["choices"][0]["message"]["content"]
            model = payload.get("model") or self.model
        except (ValueError, KeyError, IndexError, TypeError):
            raise LLMError("unexpected reply format from the language model") from None
        return LLMResponse(data=extract_json(content), model=str(model), latency_ms=latency)
