import pymupdf

from app.orchestration.ingestion.extractors import (
    PlainTextExtractor,
    PyMuPDFTextExtractor,
)


def _tiny_pdf(pages: int = 3, with_toc: bool = True) -> bytes:
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Page {i + 1} content for extraction.")
    if with_toc:
        doc.set_toc([[1, "First Chapter", 1], [1, "Second Chapter", 2]])
    data = doc.tobytes()
    doc.close()
    return data


def test_plain_text_extractor_passthrough() -> None:
    document = PlainTextExtractor().extract(b"hello\n\nworld")

    assert len(document.pages) == 1
    assert document.pages[0].ordinal == 1
    assert "world" in document.pages[0].text


def test_pymupdf_extractor_reads_pages_metadata_and_toc() -> None:
    document = PyMuPDFTextExtractor().extract(_tiny_pdf(3))

    assert len(document.pages) == 3
    assert document.pages[2].ordinal == 3
    assert "Page 3 content" in document.pages[2].text
    assert [(e.level, e.title, e.page) for e in document.toc] == [
        (1, "First Chapter", 1),
        (1, "Second Chapter", 2),
    ]


def test_pymupdf_extractor_without_toc() -> None:
    document = PyMuPDFTextExtractor().extract(_tiny_pdf(2, with_toc=False))

    assert document.toc == []
