from app.core.config import Settings
from app.llm.openai_compat import OpenAICompatEmbeddingProvider, OpenAICompatLLMProvider
from app.llm.protocols import EmbeddingProvider, LLMProvider


class ProviderNotConfiguredError(RuntimeError):
    pass


def build_llm_provider(settings: Settings) -> LLMProvider | None:
    if (
        not settings.openai_base_url
        or not settings.openai_api_key
        or not settings.llm_model
    ):
        return None
    return OpenAICompatLLMProvider(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.llm_model,
    )


def build_embedding_provider(settings: Settings) -> EmbeddingProvider | None:
    if (
        not settings.openai_base_url
        or not settings.openai_api_key
        or not settings.embedding_model
    ):
        return None
    return OpenAICompatEmbeddingProvider(
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key.get_secret_value(),
        model=settings.embedding_model,
        dimension=settings.embedding_dimension,
    )
