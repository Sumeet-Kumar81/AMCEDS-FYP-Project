"""Deterministic stand-in for the language model, for tests only (B1-A2-02). SIMULATED.

It is never selected by ``LLM_PROVIDER``: nothing in the running system can silently use made-up
model answers. Give it either a list of replies (returned in order) or a function of the prompt.
A reply may be a dict (the JSON object), a string (raw model text, parsed like a real reply) or an
exception instance (raised, e.g. ``LLMTimeout()``). Every call is recorded in ``calls``.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from app.llm.gateway import LLMClient, LLMError, LLMResponse, extract_json

Reply = dict[str, Any] | str | BaseException


class FakeLLMClient(LLMClient):
    provider = "fake"

    def __init__(self, replies: Iterable[Reply] | Callable[[str, str], Reply] = (),
                 model: str = "SIMULATED-fake-model", latency_ms: int = 5) -> None:
        self.model = model
        self._fn = replies if callable(replies) else None
        self._queue = [] if callable(replies) else list(replies)
        self._latency = latency_ms
        self.calls: list[tuple[str, str]] = []

    async def complete_json(self, system: str, user: str) -> LLMResponse:
        self.calls.append((system, user))
        if self._fn is not None:
            reply = self._fn(system, user)
        elif self._queue:
            reply = self._queue.pop(0)
        else:
            raise LLMError("fake model has no reply left")
        if isinstance(reply, BaseException):
            raise reply
        data = extract_json(reply) if isinstance(reply, str) else dict(reply)
        return LLMResponse(data=data, model=self.model, latency_ms=self._latency)
