from uuid import UUID

import pytest

from app.llm.protocols import LLMMessage
from app.orchestration.ask import BookNotReadyError, intersect_citations
from app.orchestration.ask_schemas import (
    INSUFFICIENT_EVIDENCE_MESSAGE,
    AskLLMResponse,
)
from app.retrieval.protocols import RetrievedChunk
from tests.scripted import ScriptedLLM


def _chunk(chunk_id: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=UUID(chunk_id),
        workspace_id=UUID(int=1),
        book_id=UUID(int=2),
        chapter_id=UUID(int=3),
        section="Ch. 1 > Background",
        page_start=41,
        page_end=42,
        text="passage text",
        score=0.9,
    )


def test_ask_llm_response_parses_camel_case() -> None:
    parsed = AskLLMResponse.model_validate(
        {
            "answer": "Volatile is not atomic (Ch. 2, pp. 7-8).",
            "bookGrounded": True,
            "citations": [{"chunkId": "abc"}],
            "insufficientEvidence": False,
            "generalKnowledgeNote": None,
        }
    )

    assert parsed.book_grounded is True
    assert parsed.citations[0].chunk_id == "abc"
    assert parsed.insufficient_evidence is False


def test_ask_llm_response_rejects_blank_answer() -> None:
    with pytest.raises(Exception, match="answer"):
        AskLLMResponse.model_validate(
            {"answer": "  ", "bookGrounded": True, "citations": []}
        )


def test_intersect_citations_keeps_only_retrieved_in_order() -> None:
    a, b = str(UUID(int=17)), str(UUID(int=18))
    fake = str(UUID(int=15))

    kept = intersect_citations([fake, b, a, a], [_chunk(a), _chunk(b)])

    assert [str(chunk.chunk_id) for chunk in kept] == [b, a]


def test_intersect_citations_empty_when_nothing_matches() -> None:
    assert intersect_citations([str(UUID(int=15))], [_chunk(str(UUID(int=16)))]) == []


def test_scripted_llm_returns_responses_in_order() -> None:
    llm = ScriptedLLM(["first", "second"])

    first = llm.complete([LLMMessage("user", "hi")])
    second = llm.complete([LLMMessage("user", "again")])

    assert first.text == "first"
    assert second.text == "second"
    assert len(llm.calls) == 2


def test_insufficient_message_is_exact_contract() -> None:
    assert INSUFFICIENT_EVIDENCE_MESSAGE == (
        "I could not find enough material in this book to answer confidently."
    )


def test_book_not_ready_error_is_runtime_error() -> None:
    assert issubclass(BookNotReadyError, RuntimeError)
