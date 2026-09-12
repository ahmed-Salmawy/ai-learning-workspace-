import json
from uuid import uuid4

import pytest

from app.engines.llm_roadmap import LLMRoadmapEngine, normalize_name
from app.engines.protocols import ExtractedConcept
from app.llm.protocols import LLMCompletion, LLMMessage


class ScriptedLLM:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
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
        if not self._responses:
            raise AssertionError("ScriptedLLM ran out of responses")
        text = self._responses.pop(0)
        return LLMCompletion(text=text, model=model or "scripted")


def test_normalize_name() -> None:
    assert normalize_name("  Retrieval-Augmented  Generation (RAG) ") == (
        "retrieval augmented generation rag"
    )
    assert normalize_name("RAG") == "rag"


def test_extract_concepts_parses_and_dedups() -> None:
    payload = {
        "concepts": [
            {"name": "RAG", "description": "Retrieval augmented generation"},
            {"name": "rag", "description": "duplicate spelling"},
            {"name": "Embeddings", "description": None},
        ]
    }
    engine = LLMRoadmapEngine(ScriptedLLM([json.dumps(payload)]))

    concepts = engine.extract_concepts(workspace_id=uuid4(), book_id=uuid4(), chunk_texts=["t"])

    names = [c.normalized_name for c in concepts]
    assert names == ["rag", "embeddings"]
    assert concepts[0].description == "Retrieval augmented generation"


def test_extract_concepts_retries_on_invalid_json() -> None:
    good = json.dumps({"concepts": [{"name": "Prompting"}]})
    llm = ScriptedLLM(["not json at all", good])
    engine = LLMRoadmapEngine(llm)

    concepts = engine.extract_concepts(workspace_id=uuid4(), book_id=uuid4(), chunk_texts=["t"])

    assert [c.name for c in concepts] == ["Prompting"]
    assert len(llm.calls) == 2


def test_extract_concepts_retries_on_schema_violation() -> None:
    good = json.dumps({"concepts": [{"name": "Agents"}]})
    bad = json.dumps({"concepts": [{"description": "missing name"}]})
    llm = ScriptedLLM([bad, good])
    engine = LLMRoadmapEngine(llm)

    concepts = engine.extract_concepts(workspace_id=uuid4(), book_id=uuid4(), chunk_texts=["t"])

    assert [c.name for c in concepts] == ["Agents"]


def test_extract_concepts_hard_fails_after_budget() -> None:
    llm = ScriptedLLM(["nope", "still nope", "nope again"])
    engine = LLMRoadmapEngine(llm)

    with pytest.raises(ValueError, match="failed validation"):
        engine.extract_concepts(workspace_id=uuid4(), book_id=uuid4(), chunk_texts=["t"])
    assert len(llm.calls) == 3


def test_extract_concepts_parses_fenced_json() -> None:
    fenced = '```json\n{"concepts": [{"name": "Vector search"}]}\n```'
    engine = LLMRoadmapEngine(ScriptedLLM([fenced]))

    concepts = engine.extract_concepts(workspace_id=uuid4(), book_id=uuid4(), chunk_texts=["t"])

    assert [c.name for c in concepts] == ["Vector search"]


def test_build_dependencies_drops_unknown_refs_and_self_edges() -> None:
    payload = {
        "relationships": [
            {
                "fromConcept": "Embeddings",
                "toConcept": "Vector search",
                "relation": "PREREQUISITE_OF",
                "confidence": 0.9,
            },
            {
                "fromConcept": "Embeddings",
                "toConcept": "Nonexistent",
                "relation": "PREREQUISITE_OF",
            },
            {"fromConcept": "RAG", "toConcept": "RAG", "relation": "RELATED_TO"},
            {
                "fromConcept": "rag",
                "toConcept": "vector search",
                "relation": "RELATED_TO",
                "confidence": 0.4,
            },
        ]
    }
    engine = LLMRoadmapEngine(ScriptedLLM([json.dumps(payload)]))
    concepts = [
        ExtractedConcept(name="RAG", normalized_name="rag", description=None),
        ExtractedConcept(name="Embeddings", normalized_name="embeddings", description=None),
        ExtractedConcept(
            name="Vector search", normalized_name="vector search", description=None
        ),
    ]

    edges = engine.build_dependencies(workspace_id=uuid4(), book_id=uuid4(), concepts=concepts)

    assert len(edges) == 2
    assert edges[0].from_concept == "Embeddings"
    assert edges[0].to_concept == "Vector search"
    assert edges[0].relation == "PREREQUISITE_OF"
    assert edges[1].from_concept == "RAG"
    assert edges[1].relation == "RELATED_TO"


def test_build_dependencies_empty_concepts_short_circuits() -> None:
    engine = LLMRoadmapEngine(ScriptedLLM([]))

    assert (
        engine.build_dependencies(workspace_id=uuid4(), book_id=uuid4(), concepts=[])
        == []
    )



def test_engine_satisfies_protocol() -> None:
    from app.engines.protocols import RoadmapEngine

    engine: RoadmapEngine = LLMRoadmapEngine(
        ScriptedLLM([json.dumps({"concepts": []})])
    )
    assert engine is not None
