"""LLM Gateway tests (B1-A2-02). No network: every HTTP call goes to an httpx MockTransport."""
from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from app.llm.fake import FakeLLMClient
from app.llm.gateway import GROQ_BASE_URL, LLMError, LLMTimeout, extract_json, get_llm_client
from app.llm.ollama import OllamaClient
from app.llm.openai_compatible import OpenAICompatibleClient

KEY = "SIMULATED-not-a-real-key-123"


def chat_reply(content: str, model: str = "llama-SIMULATED") -> dict:
    return {"model": model, "choices": [{"message": {"role": "assistant", "content": content}}]}


def groq(handler) -> tuple[OpenAICompatibleClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    client = OpenAICompatibleClient(base_url=GROQ_BASE_URL, api_key=KEY, model="llama-3.3-70b-versatile",
                                    provider="groq", transport=httpx.MockTransport(wrapped))
    return client, seen


# ---------------------------------------------------------------- OpenAI-compatible (Groq)
async def test_valid_json_reply_with_model_and_latency() -> None:
    client, seen = groq(lambda r: httpx.Response(200, json=chat_reply('{"incident_type": "fire"}')))
    reply = await client.complete_json("system text", "user text")
    assert reply.data == {"incident_type": "fire"} and reply.model == "llama-SIMULATED" and reply.latency_ms >= 0
    body = json.loads(seen[0].content)
    assert str(seen[0].url) == f"{GROQ_BASE_URL}/chat/completions"
    assert body["temperature"] == 0 and body["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert seen[0].headers["authorization"] == f"Bearer {KEY}"


async def test_invalid_json_is_a_permanent_llm_error() -> None:
    client, _ = groq(lambda r: httpx.Response(200, json=chat_reply("sorry, I cannot help")))
    with pytest.raises(LLMError) as err:
        await client.complete_json("s", "u")
    assert not err.value.transient and not isinstance(err.value, LLMTimeout)


async def test_timeout_is_llm_timeout_and_transient() -> None:
    def slow(request):
        raise httpx.ReadTimeout("SIMULATED timeout", request=request)

    client, _ = groq(slow)
    with pytest.raises(LLMTimeout) as err:
        await client.complete_json("s", "u")
    assert err.value.transient


async def test_connection_error_is_transient() -> None:
    def down(request):
        raise httpx.ConnectError("SIMULATED refused", request=request)

    client, _ = groq(down)
    with pytest.raises(LLMError) as err:
        await client.complete_json("s", "u")
    assert err.value.transient


@pytest.mark.parametrize(("status", "transient"), [(429, True), (500, True), (503, True), (400, False), (401, False)])
async def test_http_errors(status: int, transient: bool) -> None:
    client, _ = groq(lambda r: httpx.Response(status, json={"error": {"message": f"bad key {KEY}"}}))
    with pytest.raises(LLMError) as err:
        await client.complete_json("s", "u")
    assert err.value.transient is transient
    assert KEY not in str(err.value)  # the key (even echoed back by the server) never reaches our error text


async def test_unexpected_reply_shape() -> None:
    client, _ = groq(lambda r: httpx.Response(200, json={"nothing": True}))
    with pytest.raises(LLMError, match="unexpected reply format"):
        await client.complete_json("s", "u")


async def test_missing_api_key_fails_without_a_request() -> None:
    seen = []
    client = OpenAICompatibleClient(base_url=GROQ_BASE_URL, api_key="", model="m",
                                    transport=httpx.MockTransport(lambda r: seen.append(r) or httpx.Response(200)))
    assert not client.ready
    with pytest.raises(LLMError, match="LLM_API_KEY is not set"):
        await client.complete_json("s", "u")
    assert seen == []


def test_the_key_is_never_shown() -> None:
    client, _ = groq(lambda r: httpx.Response(200))
    assert KEY not in repr(client) and KEY not in str(vars(client).get("provider"))


# ---------------------------------------------------------------- Ollama
async def test_ollama_valid_reply_and_request() -> None:
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json={"model": "llama3.1:8b", "message": {"content": '{"severity": "low"}'}})

    client = OllamaClient(base_url="http://ollama:11434", model="llama3.1:8b", transport=httpx.MockTransport(handler))
    reply = await client.complete_json("s", "u")
    body = json.loads(seen[0].content)
    assert reply.data == {"severity": "low"} and reply.model == "llama3.1:8b"
    assert str(seen[0].url) == "http://ollama:11434/api/chat"
    assert body["format"] == "json" and body["stream"] is False and body["options"]["temperature"] == 0


async def test_ollama_timeout() -> None:
    def slow(request):
        raise httpx.ReadTimeout("SIMULATED", request=request)

    with pytest.raises(LLMTimeout):
        await OllamaClient(base_url="http://x", model="m", transport=httpx.MockTransport(slow)).complete_json("s", "u")


# ---------------------------------------------------------------- JSON extraction
@pytest.mark.parametrize("text", ['{"a": 1}', '```json\n{"a": 1}\n```', 'Here it is: {"a": 1} done', '  {"a":1}\n'])
def test_extract_json_accepts_an_object(text: str) -> None:
    assert extract_json(text) == {"a": 1}


@pytest.mark.parametrize("text", ["", "   ", "no json here", "[1, 2]", '{"a": }'])
def test_extract_json_rejects_everything_else(text: str) -> None:
    with pytest.raises(LLMError):
        extract_json(text)


# ---------------------------------------------------------------- provider switch by configuration
def cfg(**kw) -> SimpleNamespace:
    base = dict(llm_provider="groq", llm_model="llama-3.3-70b-versatile", llm_api_key=KEY, llm_base_url="",
                llm_timeout_s=8.0, ollama_url="http://ollama:11434")
    return SimpleNamespace(**{**base, **kw})


def test_provider_groq() -> None:
    client = get_llm_client(cfg())
    assert isinstance(client, OpenAICompatibleClient) and client.provider == "groq" and client.ready
    assert client._url == f"{GROQ_BASE_URL}/chat/completions" and client._timeout == 8.0


def test_provider_ollama() -> None:
    client = get_llm_client(cfg(llm_provider="OLLAMA", llm_model="llama3.1:8b"))
    assert isinstance(client, OllamaClient) and client.model == "llama3.1:8b"


@pytest.mark.parametrize("name", ["gemini", "fake", "", "openai"])
def test_unsupported_providers_are_refused(name: str) -> None:
    """The fake model can never be switched on by configuration (no made-up answers in a running system)."""
    with pytest.raises(ValueError, match="not supported"):
        get_llm_client(cfg(llm_provider=name))


def test_default_timeout_protects_nfr_p1() -> None:
    from app.core.config import Settings

    assert Settings().llm_timeout_s == 8.0


# ---------------------------------------------------------------- fake model
async def test_fake_model_replies_in_order_and_records_calls() -> None:
    fake = FakeLLMClient([{"a": 1}, '{"b": 2}', LLMTimeout()])
    assert (await fake.complete_json("s", "u1")).data == {"a": 1}
    assert (await fake.complete_json("s", "u2")).data == {"b": 2}
    with pytest.raises(LLMTimeout):
        await fake.complete_json("s", "u3")
    with pytest.raises(LLMError, match="no reply left"):
        await fake.complete_json("s", "u4")
    assert [u for _, u in fake.calls] == ["u1", "u2", "u3", "u4"] and fake.model.startswith("SIMULATED")
