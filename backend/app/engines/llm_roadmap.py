import logging
import re
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.engines.protocols import ExtractedConcept, ExtractedRelationship
from app.engines.schemas import ConceptListOut, RelationshipListOut
from app.llm.protocols import LLMProvider
from app.llm.structured import structured_call

logger = logging.getLogger(__name__)

EXTRACT_SYSTEM_PROMPT = (
    "You extract learning concepts from book passages. Respond with ONLY a JSON object "
    'of shape {"concepts": [{"name": "...", "description": "..."}]}. '
    "Use the book's terminology. No prose outside the JSON."
)

DEPENDENCIES_SYSTEM_PROMPT = (
    "You identify prerequisite and related-concept edges between the given concepts. "
    "Respond with ONLY a JSON object of shape "
    '{"relationships": [{"fromConcept": "...", "toConcept": "...", '
    '"relation": "PREREQUISITE_OF|RELATED_TO|CONTRASTS_WITH|IMPLEMENTED_BY|CAUSES|'
    'PREVENTS|EXAMPLE_OF|PART_OF", "confidence": 0.0}]}. '
    "fromConcept and toConcept MUST be names from the provided list. "
    "No prose outside the JSON."
)


def normalize_name(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    return normalized[:512]


class LLMRoadmapEngine:
    def __init__(self, llm_provider: LLMProvider, model: str | None = None) -> None:
        self._llm = llm_provider
        self._model = model

    def extract_concepts(
        self, *, workspace_id: UUID, book_id: UUID, chunk_texts: list[str]
    ) -> list[ExtractedConcept]:
        concepts: list[ExtractedConcept] = []
        seen: set[str] = set()
        for batch in batch_texts(chunk_texts):
            prompt = (
                "Extract the distinct learning concepts from these book passages:\n\n"
                + "\n\n".join(batch)
            )
            raw = self._structured_call(EXTRACT_SYSTEM_PROMPT, prompt, ConceptListOut)
            for item in raw.concepts:
                normalized = normalize_name(item.name)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                concepts.append(
                    ExtractedConcept(
                        name=item.name,
                        normalized_name=normalized,
                        description=item.description,
                    )
                )
        return concepts

    def build_dependencies(
        self, *, workspace_id: UUID, book_id: UUID, concepts: list[ExtractedConcept]
    ) -> list[ExtractedRelationship]:
        if not concepts:
            return []
        names = [concept.name for concept in concepts]
        known = {normalize_name(name) for name in names}
        name_by_normalized = {normalize_name(concept.name): concept.name for concept in concepts}
        prompt = (
            "Concepts:\n- " + "\n- ".join(names) + "\n\nIdentify the meaningful edges."
        )
        raw = self._structured_call(DEPENDENCIES_SYSTEM_PROMPT, prompt, RelationshipListOut)
        relationships: list[ExtractedRelationship] = []
        seen: set[tuple[str, str, str]] = set()
        for item in raw.relationships:
            from_normalized = normalize_name(item.from_concept)
            to_normalized = normalize_name(item.to_concept)
            if from_normalized not in known or to_normalized not in known:
                continue
            key = (from_normalized, to_normalized, item.relation)
            if key in seen or from_normalized == to_normalized:
                continue
            seen.add(key)
            relationships.append(
                ExtractedRelationship(
                    from_concept=name_by_normalized[from_normalized],
                    to_concept=name_by_normalized[to_normalized],
                    relation=key[2],
                    confidence=item.confidence,
                )
            )
        return relationships

    def _structured_call(
        self, system_prompt: str, user_prompt: str, schema: type[BaseModel]
    ) -> Any:
        return structured_call(
            self._llm, system_prompt, user_prompt, schema, model=self._model
        )


def batch_texts(texts: list[str], max_chars: int = 12000) -> list[list[str]]:
    batches: list[list[str]] = []
    current: list[str] = []
    size = 0
    for text in texts:
        if current and size + len(text) > max_chars:
            batches.append(current)
            current, size = [], 0
        current.append(text)
        size += len(text)
    if current:
        batches.append(current)
    return batches
