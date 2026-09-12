import logging
import time
from typing import Any

from pydantic import BaseModel, ValidationError

from app.llm.openai_compat import parse_json_object
from app.llm.protocols import LLMMessage, LLMProvider

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 0.5


def structured_call(
    llm: LLMProvider,
    system_prompt: str,
    user_prompt: str,
    schema: type[BaseModel],
    *,
    model: str | None = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> Any:
    messages = [
        LLMMessage("system", system_prompt),
        LLMMessage("user", user_prompt),
    ]
    feedback = ""
    for attempt in range(max_attempts):
        user_content = user_prompt if not feedback else user_prompt + "\n\n" + feedback
        messages[-1] = LLMMessage("user", user_content)
        completion = llm.complete(
            messages,
            model=model,
            temperature=0.0,
            json_schema={"type": "object"},
        )
        try:
            return schema.model_validate(parse_json_object(completion.text))
        except (ValidationError, ValueError) as exc:
            feedback = (
                f"Your previous response was invalid: {exc}. "
                "Return ONLY the corrected JSON object."
            )
            logger.warning(
                "structured output rejected (attempt %d/%d): %s",
                attempt + 1,
                max_attempts,
                exc,
            )
            if attempt + 1 < max_attempts:
                time.sleep(RETRY_BACKOFF_SECONDS)
    raise ValueError(
        f"structured output failed validation after {max_attempts} attempts"
    )
