"""Local open-weight model through Ollama's HTTP API (``/api/chat``). Task B1-A2-02, D-008.

Temperature 0, ``format: json``, no streaming. Works offline once the model is pulled.
"""
from __future__ import annotations

import time

import httpx

from app.llm.gateway import DEFAULT_TIMEOUT_S, LLMClient, LLMError, LLMResponse, LLMTimeout, extract_json


class OllamaClient(LLMClient):
    provider = "ollama"

    def __init__(self, *, base_url: str, model: str, timeout_s: float = DEFAULT_TIMEOUT_S,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.model = model
        self._url = base_url.rstrip("/") + "/api/chat"
        self._timeout = timeout_s
        self._transport = transport

    @property
    def ready(self) -> bool:
        return bool(self.model)

    async def complete_json(self, system: str, user: str) -> LLMResponse:
        body = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                reply = await client.post(self._url, json=body)
        except httpx.TimeoutException:
            raise LLMTimeout() from None
        except httpx.HTTPError as exc:
            raise LLMError(f"cannot reach Ollama ({exc.__class__.__name__})", transient=True) from None
        latency = round((time.perf_counter() - started) * 1000)
        if reply.status_code >= 400:
            raise LLMError(f"Ollama returned HTTP {reply.status_code}", transient=reply.status_code >= 500)
        try:
            payload = reply.json()
            content = payload["message"]["content"]
        except (ValueError, KeyError, TypeError):
            raise LLMError("unexpected reply format from Ollama") from None
        return LLMResponse(data=extract_json(content), model=str(payload.get("model") or self.model), latency_ms=latency)
