from app.orchestration.ingestion.extract import ExtractedDocument, ExtractedPage, TOCEntry
from app.orchestration.ingestion.toc import detect_toc


def _document(
    pages: dict[int, str], toc: list[TOCEntry] | None = None
) -> ExtractedDocument:
    return ExtractedDocument(
        pages=[ExtractedPage(ordinal=n, text=t) for n, t in sorted(pages.items())],
        toc=toc or [],
    )


def test_embedded_toc_wins() -> None:
    toc = [
        TOCEntry(level=1, title="Introduction", page=1),
        TOCEntry(level=2, title="1.1 Background", page=2),
        TOCEntry(level=1, title="Methods", page=5),
        TOCEntry(level=1, title="Results", page=9),
    ]
    detection = detect_toc(_document({i: "text" for i in range(1, 12)}, toc))

    assert detection.source == "TOC"
    assert detection.confidence == 0.9
    assert [c.ordinal for c in detection.chapters] == [1, 2, 3]
    assert detection.chapters[0].page_start == 1
    assert detection.chapters[0].page_end == 4
    assert detection.chapters[1].page_start == 5
    assert detection.chapters[1].page_end == 8
    assert detection.chapters[2].page_end == 11


def test_heuristic_fallback_when_no_embedded_toc() -> None:
    pages = {
        1: "Title page\nsome intro text",
        2: "Chapter 1: Getting Started\ncontent here",
        3: "more content",
        4: "Chapter 2: Going Deeper\nother content",
    }
    detection = detect_toc(_document(pages))

    assert detection.source == "INFERRED"
    assert detection.confidence == 0.5
    assert len(detection.chapters) == 2
    assert detection.chapters[0].title == "Chapter 1: Getting Started"
    assert detection.chapters[0].page_start == 2
    assert detection.chapters[0].page_end == 3
    assert detection.chapters[1].page_start == 4


def test_single_level_one_entry_falls_back_to_heuristics() -> None:
    detection = detect_toc(_document({1: "no chapter markers"}))

    assert detection.source == "INFERRED"
    assert detection.chapters == []


def test_no_chapters_detected() -> None:
    detection = detect_toc(_document({1: "plain text, no markers"}))

    assert detection.chapters == []
    assert detection.source == "INFERRED"
