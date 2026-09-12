import hashlib
from collections.abc import Sequence
from typing import Any

from app.llm.protocols import LLMCompletion, LLMMessage


class InMemoryLLMProvider:
    def __init__(
        self,
        responses: Sequence[str] | None = None,
        default_response: str = "{}",
        model: str = "fake-llm",
    ) -> None:
        self._responses = list(responses) if responses else []
        self._default_response = default_response
        self._model = model
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMCompletion:
        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "json_schema": json_schema,
            }
        )
        text = self._responses.pop(0) if self._responses else self._default_response
        return LLMCompletion(
            text=text,
            model=model or self._model,
            prompt_tokens=sum(len(m.content) for m in messages),
            completion_tokens=len(text),
        )


def deterministic_vector(text: str, dimension: int = 1536) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    counter = 0
    while len(values) < dimension:
        chunk = hashlib.sha256(digest + counter.to_bytes(4, "big")).digest()
        values.extend(byte / 255.0 for byte in chunk)
        counter += 1
    return values[:dimension]


class InMemoryEmbeddingProvider:
    def __init__(self, dimension: int = 1536, model: str = "fake-embedding") -> None:
        self._dimension = dimension
        self._model = model

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model(self) -> str:
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [deterministic_vector(t, self._dimension) for t in texts]
