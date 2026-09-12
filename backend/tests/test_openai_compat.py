import json
from collections.abc import Callable

import httpx
import pytest

from app.llm.openai_compat import (
    OpenAICompatEmbeddingProvider,
    OpenAICompatError,
    OpenAICompatLLMProvider,
    parse_json_object,
)
from app.llm.protocols import LLMMessage

Handler = Callable[[httpx.Request], httpx.Response]


def _transport(handler: Handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def test_llm_provider_sends_auth_and_parses_response() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "gpt-test",
                "choices": [{"message": {"content": "hello"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 1},
            },
        )

    provider = OpenAICompatLLMProvider(
        base_url="https://llm.example/v1",
        api_key="secret-key",
        model="gpt-test",
        transport=_transport(handler),
    )
    completion = provider.complete([LLMMessage("user", "hi")], temperature=0.2)

    assert seen["url"].endswith("/v1/chat/completions")
    assert seen["auth"] == "Bearer secret-key"
    assert seen["payload"]["model"] == "gpt-test"
    assert seen["payload"]["temperature"] == 0.2
    assert completion.text == "hello"
    assert completion.prompt_tokens == 5
    assert completion.completion_tokens == 1


def test_llm_provider_json_mode_sets_response_format() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{}"}}], "model": "m"},
        )

    provider = OpenAICompatLLMProvider(
        base_url="https://llm.example", api_key="k", model="m",
        transport=_transport(handler),
    )
    provider.complete([LLMMessage("user", "hi")], json_schema={"type": "object"})

    assert seen["payload"]["response_format"] == {"type": "json_object"}


def test_llm_provider_error_status_raises() -> None:
    provider = OpenAICompatLLMProvider(
        base_url="https://llm.example", api_key="k", model="m",
        transport=_transport(lambda request: httpx.Response(429, text="rate limited")),
    )

    with pytest.raises(OpenAICompatError, match="429"):
        provider.complete([LLMMessage("user", "hi")])


def test_embedding_provider_sorts_by_index() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload == {"model": "embed-test", "input": ["a", "b"]}
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.4, 0.5]},
                    {"index": 0, "embedding": [0.1, 0.2]},
                ]
            },
        )

    provider = OpenAICompatEmbeddingProvider(
        base_url="https://llm.example", api_key="k", model="embed-test",
        dimension=2, transport=_transport(handler),
    )

    vectors = provider.embed(["a", "b"])

    assert vectors == [[0.1, 0.2], [0.4, 0.5]]
    assert provider.dimension == 2
    assert provider.model == "embed-test"


def test_embedding_provider_empty_input_short_circuits() -> None:
    provider = OpenAICompatEmbeddingProvider(
        base_url="https://llm.example", api_key="k", model="m", dimension=3,
        transport=_transport(lambda request: httpx.Response(200, json={"data": []})),
    )

    assert provider.embed([]) == []


def test_parse_json_object_handles_fences_and_non_objects() -> None:
    assert parse_json_object('{"a": 1}') == {"a": 1}
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(ValueError, match="expected a JSON object"):
        parse_json_object("[1, 2]")
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_json_object("nope")
