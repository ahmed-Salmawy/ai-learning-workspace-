import copy
from collections.abc import Sequence
from uuid import UUID

from app.engines.protocols import ExtractedConcept, ExtractedRelationship


class InMemoryRoadmapEngine:
    def __init__(
        self,
        concepts: Sequence[ExtractedConcept] = (),
        relationships: Sequence[ExtractedRelationship] = (),
    ) -> None:
        self._concepts = list(concepts)
        self._relationships = list(relationships)
        self.extract_calls = 0
        self.dependency_calls = 0

    def extract_concepts(
        self, *, workspace_id: UUID, book_id: UUID, chunk_texts: list[str]
    ) -> list[ExtractedConcept]:
        self.extract_calls += 1
        return copy.deepcopy(self._concepts)

    def build_dependencies(
        self, *, workspace_id: UUID, book_id: UUID, concepts: list[ExtractedConcept]
    ) -> list[ExtractedRelationship]:
        self.dependency_calls += 1
        return copy.deepcopy(self._relationships)
