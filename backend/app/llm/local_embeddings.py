import logging
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class SentenceTransformerEmbeddingProvider:
    def __init__(self, model_name: str, dimension: int) -> None:
        self._model_name = model_name
        self._dimension = dimension
        self._model = _load_model(model_name)

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model(self) -> str:
        return f"local-sentence-transformers/{self._model_name}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(
            texts, batch_size=64, show_progress_bar=False, normalize_embeddings=True
        )
        return [vector.tolist() for vector in vectors]


@lru_cache
def _load_model(model_name: str) -> "SentenceTransformer":
    from sentence_transformers import SentenceTransformer

    logger.info("loading local embedding model %s (first run may download it)", model_name)
    return SentenceTransformer(model_name)
