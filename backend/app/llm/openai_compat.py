import json
import time
from typing import Any

import httpx

from app.core.metrics import METRICS
from app.llm.protocols import LLMCompletion, LLMMessage


class OpenAICompatError(RuntimeError):
    pass


class OpenAICompatLLMProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMCompletion:
        payload: dict[str, Any] = {
            "model": model or self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if json_schema is not None:
            payload["response_format"] = {"type": "json_object"}
        start = time.perf_counter()
        response = self._client.post("/chat/completions", json=payload)
        METRICS.observe("llm_latency_seconds", time.perf_counter() - start, kind="chat")
        METRICS.increment("llm_calls_total", kind="chat")
        if response.status_code != 200:
            raise OpenAICompatError(
                f"chat/completions failed: {response.status_code} {response.text[:500]}"
            )
        body = response.json()
        try:
            text = body["choices"][0]["message"]["content"]
            usage = body.get("usage", {})
            if usage.get("prompt_tokens"):
                METRICS.increment(
                    "llm_tokens_total",
                    value=usage["prompt_tokens"],
                    kind="chat",
                    direction="prompt",
                )
            if usage.get("completion_tokens"):
                METRICS.increment(
                    "llm_tokens_total",
                    value=usage["completion_tokens"],
                    kind="chat",
                    direction="completion",
                )
            return LLMCompletion(
                text=text,
                model=body.get("model", model or self._model),
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenAICompatError(f"unexpected chat response shape: {body}") from exc


class OpenAICompatEmbeddingProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        dimension: int,
        timeout: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._model = model
        self._dimension = dimension
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            transport=transport,
        )

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model(self) -> str:
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        start = time.perf_counter()
        response = self._client.post(
            "/embeddings", json={"model": self._model, "input": texts}
        )
        METRICS.observe("llm_latency_seconds", time.perf_counter() - start, kind="embeddings")
        METRICS.increment("llm_calls_total", kind="embeddings")
        if response.status_code != 200:
            raise OpenAICompatError(
                f"embeddings failed: {response.status_code} {response.text[:500]}"
            )
        body = response.json()
        try:
            data = sorted(body["data"], key=lambda item: item["index"])
            return [list(item["embedding"]) for item in data]
        except (KeyError, TypeError) as exc:
            raise OpenAICompatError(f"unexpected embeddings response shape: {body}") from exc


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("```", 2)[1]
        if stripped.startswith("json"):
            stripped = stripped[4:]
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("expected a JSON object")
    return parsed
