"""LLM Gateway (SDS 3.2). One interface so the model can be swapped by config only. Day 5."""
from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    async def complete_json(self, system: str, user: str) -> dict:
        """Return parsed JSON, temperature 0. Raise on invalid JSON (caller retries once)."""


# TODO Day 5: GroqClient, GeminiClient, OllamaClient + get_llm_client() from settings.llm_provider
