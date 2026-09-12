from app.orchestration.ingestion.chunking import (
    MAX_PAGE_SPAN,
    chunk_document,
    content_hash,
    estimate_tokens,
)
from app.orchestration.ingestion.extract import ExtractedDocument, ExtractedPage
from app.orchestration.ingestion.toc import DetectedChapter

_PARAGRAPH = (
    "Neural networks transform inputs through stacked layers of learned representations. "
    "Each layer applies weights, biases, and nonlinear activations to its inputs. "
    "Training adjusts these parameters to minimize prediction error on examples. "
) * 5  # ~760 chars; two paragraphs of this ≈ 380 tokens


def _document(pages: dict[int, str]) -> ExtractedDocument:
    return ExtractedDocument(
        pages=[ExtractedPage(ordinal=n, text=text) for n, text in sorted(pages.items())]
    )


def _chapter(ordinal: int, start: int, end: int | None) -> DetectedChapter:
    return DetectedChapter(
        ordinal=ordinal,
        title=f"Chapter {ordinal}",
        page_start=start,
        page_end=end,
        source="TOC",
        confidence=0.9,
    )


def test_chunks_respect_chapter_boundaries() -> None:
    document = _document({1: _PARAGRAPH + "\n\n" + _PARAGRAPH, 2: _PARAGRAPH + "\n\n" + _PARAGRAPH})
    chapters = [_chapter(1, 1, 1), _chapter(2, 2, 2)]

    drafts = chunk_document(document, chapters)

    assert drafts
    assert {draft.chapter_ordinal for draft in drafts} == {1, 2}
    for draft in drafts:
        assert draft.page_start == draft.page_end


def test_chunk_never_spans_more_than_max_pages() -> None:
    document = _document({i: _PARAGRAPH for i in range(1, 9)})
    chapters = [_chapter(1, 1, 8)]

    drafts = chunk_document(document, chapters)

    assert len(drafts) > 1
    for draft in drafts:
        assert draft.page_end - draft.page_start < MAX_PAGE_SPAN


def test_oversized_single_paragraph_is_split() -> None:
    big = "Sentence ends here. " * 400
    document = _document({1: big})
    chapters = [_chapter(1, 1, 1)]

    drafts = chunk_document(document, chapters)

    assert len(drafts) > 1
    for draft in drafts:
        assert estimate_tokens(draft.text) <= 600
    assert all(draft.page_start == 1 for draft in drafts)


def test_content_hash_normalizes_whitespace() -> None:
    assert content_hash("hello   world\n\nnext") == content_hash("hello world next")
    assert content_hash("a") != content_hash("b")


def test_empty_document_yields_no_chunks() -> None:
    document = _document({1: "", 2: "   \n  "})
    chapters = [_chapter(1, 1, 2)]

    assert chunk_document(document, chapters) == []


def test_pages_outside_any_chapter_are_skipped() -> None:
    document = _document({1: _PARAGRAPH, 2: _PARAGRAPH})
    chapters = [_chapter(1, 2, 2)]

    drafts = chunk_document(document, chapters)

    assert all(draft.page_start >= 2 for draft in drafts)
