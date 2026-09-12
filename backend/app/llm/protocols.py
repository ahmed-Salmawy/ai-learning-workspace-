from typing import Any, Protocol, runtime_checkable

MessageRole = str  # "system" | "user" | "assistant"


class LLMMessage:
    __slots__ = ("role", "content")

    def __init__(self, role: MessageRole, content: str) -> None:
        self.role = role
        self.content = content


class LLMCompletion:
    __slots__ = ("text", "model", "prompt_tokens", "completion_tokens")

    def __init__(
        self,
        text: str,
        model: str,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ) -> None:
        self.text = text
        self.model = model
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


@runtime_checkable
class LLMProvider(Protocol):
    def complete(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMCompletion: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...

    @property
    def model(self) -> str: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...
