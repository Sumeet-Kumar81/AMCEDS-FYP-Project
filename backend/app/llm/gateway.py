"""LLM Gateway (SDS §3.2, SRS SW-3). Task B1-A2-02.

One interface, ``LLMClient.complete_json``, so the language model can be swapped by configuration
only (``LLM_PROVIDER``). Every call uses temperature 0, has a timeout (default 8 s, NFR-P1) and
returns the parsed JSON object together with the model name and latency for the audit log.

Providers (D-008, provisional, approved 2026-11-21 by the project developer):
  * ``groq``   – hosted Llama through Groq's OpenAI-compatible HTTP API (``httpx``, no vendor SDK).
                 Acceptable only because every report in this prototype is SIMULATED (NFR-C7).
  * ``ollama`` – a local open-weight model through Ollama's HTTP API.
  * ``FakeLLMClient`` (``app.llm.fake``) – deterministic replies for tests; never chosen by config.
The final default is chosen after the evaluation in B1-A2-17.

The API key comes from the environment only and is never logged or put in an error message.
Retrying on invalid JSON is the caller's job (the Triage Agent retries once with the error shown).
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

DEFAULT_TIMEOUT_S = 8.0
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class LLMError(Exception):
    """The model call failed or did not return a JSON object. ``transient`` errors may be retried."""

    def __init__(self, message: str, *, transient: bool = False) -> None:
        super().__init__(message)
        self.transient = transient


class LLMTimeout(LLMError):
    """The model did not answer in time (always transient)."""

    def __init__(self, message: str = "language model timed out") -> None:
        super().__init__(message, transient=True)


@dataclass(frozen=True)
class LLMResponse:
    data: dict[str, Any]
    model: str
    latency_ms: int


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def extract_json(text: str) -> dict[str, Any]:
    """The JSON object in a model reply. Accepts a bare object or one inside a ```json fence;
    anything else raises ``LLMError`` (not transient: the caller decides whether to ask again)."""
    if not isinstance(text, str) or not text.strip():
        raise LLMError("empty reply from the language model")
    cleaned = _FENCE.sub("", text.strip())
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise LLMError("the language model reply is not JSON") from None
        try:
            value = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError(f"the language model reply is not valid JSON: {exc.msg}") from None
    if not isinstance(value, dict):
        raise LLMError("the language model reply is JSON but not an object")
    return value


class LLMClient(ABC):
    """The replaceable gateway. Implementations must not log prompts with secrets or the API key."""

    provider: str
    model: str

    @property
    def ready(self) -> bool:
        """Whether the client is configured well enough to try a call (shown in the worker heartbeat)."""
        return True

    @abstractmethod
    async def complete_json(self, system: str, user: str) -> LLMResponse:
        """Ask the model, temperature 0, and return its JSON object. Raises ``LLMError``/``LLMTimeout``."""


def get_llm_client(settings: Any | None = None) -> LLMClient:
    """The client named by ``LLM_PROVIDER``. Unknown or unsupported providers raise ``ValueError``."""
    if settings is None:
        from app.core.config import get_settings

        settings = get_settings()
    provider = (settings.llm_provider or "").strip().lower()
    timeout = float(getattr(settings, "llm_timeout_s", DEFAULT_TIMEOUT_S))
    if provider == "groq":
        from app.llm.openai_compatible import OpenAICompatibleClient

        return OpenAICompatibleClient(base_url=getattr(settings, "llm_base_url", "") or GROQ_BASE_URL,
                                      api_key=settings.llm_api_key, model=settings.llm_model,
                                      timeout_s=timeout, provider="groq")
    if provider == "ollama":
        from app.llm.ollama import OllamaClient

        return OllamaClient(base_url=settings.ollama_url, model=settings.llm_model, timeout_s=timeout)
    raise ValueError(f"LLM_PROVIDER '{settings.llm_provider}' is not supported (use 'groq' or 'ollama', D-008)")
