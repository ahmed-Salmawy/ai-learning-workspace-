import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models import Concept, ConceptRelationship


class ConceptRepository:
    def __init__(self, session: Session, workspace_id: uuid.UUID, book_id: uuid.UUID) -> None:
        self._session = session
        self._workspace_id = workspace_id
        self._book_id = book_id

    def existing_normalized_names(self) -> set[str]:
        stmt = select(Concept.normalized_name).where(
            Concept.workspace_id == self._workspace_id,
            Concept.book_id == self._book_id,
        )
        return set(self._session.execute(stmt).scalars())

    def insert_new(
        self, concepts: Sequence[dict[str, Any]]
    ) -> tuple[int, int]:
        known = self.existing_normalized_names()
        inserted = 0
        skipped = 0
        for entry in concepts:
            normalized_name = str(entry["normalized_name"])
            if normalized_name in known:
                skipped += 1
                continue
            known.add(normalized_name)
            self._session.add(
                Concept(
                    workspace_id=self._workspace_id,
                    book_id=self._book_id,
                    name=str(entry["name"]),
                    normalized_name=normalized_name,
                    description=entry.get("description"),
                )
            )
            inserted += 1
        self._session.flush()
        return inserted, skipped

    def list(self) -> Sequence[Concept]:
        stmt = (
            select(Concept)
            .where(
                Concept.workspace_id == self._workspace_id,
                Concept.book_id == self._book_id,
            )
            .order_by(Concept.name)
        )
        return self._session.execute(stmt).scalars().all()

    def by_normalized_name(self) -> dict[str, Concept]:
        return {concept.normalized_name: concept for concept in self.list()}

    def count(self) -> int:
        stmt = select(Concept.id).where(
            Concept.workspace_id == self._workspace_id,
            Concept.book_id == self._book_id,
        )
        return len(self._session.execute(stmt).scalars().all())


class ConceptRelationshipRepository:
    def __init__(self, session: Session, workspace_id: uuid.UUID, book_id: uuid.UUID) -> None:
        self._session = session
        self._workspace_id = workspace_id
        self._book_id = book_id

    def existing_edges(self) -> set[tuple[uuid.UUID, uuid.UUID, str]]:
        stmt = select(
            ConceptRelationship.from_concept_id,
            ConceptRelationship.to_concept_id,
            ConceptRelationship.relation,
        ).where(
            ConceptRelationship.workspace_id == self._workspace_id,
            ConceptRelationship.book_id == self._book_id,
        )
        return {
            (row[0], row[1], row[2])
            for row in self._session.execute(stmt).all()
        }

    def insert_new(
        self, relationships: Sequence[dict[str, Any]], concepts_by_name: dict[str, Concept]
    ) -> tuple[int, int]:
        known = self.existing_edges()
        inserted = 0
        skipped = 0
        for entry in relationships:
            from_concept = concepts_by_name.get(str(entry["from_concept"]))
            to_concept = concepts_by_name.get(str(entry["to_concept"]))
            if from_concept is None or to_concept is None:
                skipped += 1
                continue
            edge = (from_concept.id, to_concept.id, str(entry["relation"]))
            if edge in known:
                skipped += 1
                continue
            known.add(edge)
            confidence = entry.get("confidence")
            self._session.add(
                ConceptRelationship(
                    workspace_id=self._workspace_id,
                    book_id=self._book_id,
                    from_concept_id=from_concept.id,
                    to_concept_id=to_concept.id,
                    relation=edge[2],
                    source="LLM",
                    confidence=confidence,
                )
            )
            inserted += 1
        self._session.flush()
        return inserted, skipped

    def count(self) -> int:
        stmt = select(ConceptRelationship.id).where(
            ConceptRelationship.workspace_id == self._workspace_id,
            ConceptRelationship.book_id == self._book_id,
        )
        return len(self._session.execute(stmt).scalars().all())
