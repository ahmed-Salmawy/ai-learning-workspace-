from app.llm.protocols import LLMCompletion, LLMMessage


class ScriptedLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[list[LLMMessage]] = []

    def complete(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.0,
        json_schema: dict[str, object] | None = None,
    ) -> LLMCompletion:
        self.calls.append(list(messages))
        if not self.responses:
            raise AssertionError("ScriptedLLM ran out of responses")
        text = self.responses.pop(0)
        return LLMCompletion(text=text, model=model or "scripted")
