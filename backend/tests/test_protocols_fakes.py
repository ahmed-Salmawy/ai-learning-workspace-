from uuid import UUID, uuid4

from app.engines.fakes import InMemoryRoadmapEngine
from app.engines.protocols import ExtractedConcept, ExtractedRelationship
from app.llm.fakes import InMemoryEmbeddingProvider, InMemoryLLMProvider, deterministic_vector
from app.llm.protocols import EmbeddingProvider, LLMMessage, LLMProvider
from app.retrieval.fakes import InMemoryRetrievalEngine
from app.retrieval.protocols import RetrievalEngine, RetrievedChunk
from app.storage.fakes import InMemoryObjectStorage
from app.storage.protocols import ObjectStorage


def test_llm_provider_fake_satisfies_protocol() -> None:
    provider: LLMProvider = InMemoryLLMProvider(responses=["hello world"])
    completion = provider.complete([LLMMessage("user", "hi")], json_schema={"type": "object"})

    assert completion.text == "hello world"
    assert completion.prompt_tokens == 2
    assert completion.completion_tokens == 11


def test_embedding_fake_is_deterministic_and_typed() -> None:
    provider: EmbeddingProvider = InMemoryEmbeddingProvider(dimension=8)

    vectors = provider.embed(["alpha", "alpha", "beta"])

    assert provider.dimension == 8
    assert provider.model == "fake-embedding"
    assert len(vectors) == 3
    assert all(len(v) == 8 for v in vectors)
    assert vectors[0] == vectors[1]
    assert vectors[0] != vectors[2]
    assert deterministic_vector("alpha", 8) == vectors[0]


def _make_chunk(workspace_id: UUID, book_id: UUID) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid4(),
        workspace_id=workspace_id,
        book_id=book_id,
        chapter_id=None,
        section=None,
        page_start=None,
        page_end=None,
        text="t",
        score=0.0,
    )


def test_retrieval_fake_enforces_book_isolation() -> None:
    workspace_id = uuid4()
    book_a = uuid4()
    book_b = uuid4()

    engine: RetrievalEngine = InMemoryRetrievalEngine(
        [
            _make_chunk(workspace_id, book_a),
            _make_chunk(workspace_id, book_b),
            _make_chunk(uuid4(), book_a),
        ]
    )

    results = engine.search(
        workspace_id=workspace_id, book_id=book_a, query_embedding=[0.0], top_k=10
    )

    assert len(results) == 1
    assert results[0].book_id == book_a
    assert results[0].workspace_id == workspace_id
    assert engine.search(workspace_id=uuid4(), book_id=book_a, query_embedding=[0.0]) == []


def test_retrieval_fake_respects_top_k() -> None:
    workspace_id = uuid4()
    book_id = uuid4()
    engine: RetrievalEngine = InMemoryRetrievalEngine(
        [_make_chunk(workspace_id, book_id) for _ in range(5)]
    )

    results = engine.search(
        workspace_id=workspace_id, book_id=book_id, query_embedding=[], top_k=3
    )
    assert len(results) == 3


def test_roadmap_engine_fake_returns_configured_results() -> None:
    concept = ExtractedConcept(name="RAG", normalized_name="rag", description=None)
    relationship = ExtractedRelationship(
        from_concept="rag", to_concept="embedding", relation="PREREQUISITE_OF", confidence=0.9
    )
    engine = InMemoryRoadmapEngine(concepts=[concept], relationships=[relationship])

    extracted = engine.extract_concepts(workspace_id=uuid4(), book_id=uuid4(), chunk_texts=["t"])
    edges = engine.build_dependencies(workspace_id=uuid4(), book_id=uuid4(), concepts=extracted)

    assert extracted == [concept]
    assert edges == [relationship]
    assert engine.extract_calls == 1
    assert engine.dependency_calls == 1


def test_storage_fake_round_trip() -> None:
    storage: ObjectStorage = InMemoryObjectStorage()

    stored = storage.put(
        key="ws1/book1/source.pdf", data=b"pdf-bytes", content_type="application/pdf"
    )

    assert stored.key == "ws1/book1/source.pdf"
    assert stored.size == 9
    assert storage.exists("ws1/book1/source.pdf")
    assert storage.get("ws1/book1/source.pdf") == b"pdf-bytes"
    storage.delete("ws1/book1/source.pdf")
    assert not storage.exists("ws1/book1/source.pdf")
