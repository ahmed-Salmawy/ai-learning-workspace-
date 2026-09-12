from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable
from uuid import UUID

RelationType = Literal[
    "PREREQUISITE_OF",
    "RELATED_TO",
    "CONTRASTS_WITH",
    "IMPLEMENTED_BY",
    "CAUSES",
    "PREVENTS",
    "EXAMPLE_OF",
    "PART_OF",
]


@dataclass(frozen=True)
class ExtractedConcept:
    name: str
    normalized_name: str
    description: str | None


@dataclass(frozen=True)
class ExtractedRelationship:
    from_concept: str
    to_concept: str
    relation: RelationType
    confidence: float | None


@runtime_checkable
class RoadmapEngine(Protocol):
    def extract_concepts(
        self, *, workspace_id: UUID, book_id: UUID, chunk_texts: list[str]
    ) -> list[ExtractedConcept]: ...

    def build_dependencies(
        self, *, workspace_id: UUID, book_id: UUID, concepts: list[ExtractedConcept]
    ) -> list[ExtractedRelationship]: ...
