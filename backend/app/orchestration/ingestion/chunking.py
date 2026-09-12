import hashlib
import re
from dataclasses import dataclass

from app.orchestration.ingestion.extract import ExtractedDocument, ExtractedPage
from app.orchestration.ingestion.toc import DetectedChapter, section_for_page, subsection_titles

TARGET_TOKENS_MIN = 300
TARGET_TOKENS_MAX = 600
MAX_PAGE_SPAN = 2
SENTENCE_GROUP_CHARS = 1200

_CHARS_PER_TOKEN = 4
_MIN_CHARS = TARGET_TOKENS_MIN * _CHARS_PER_TOKEN
_MAX_CHARS = TARGET_TOKENS_MAX * _CHARS_PER_TOKEN


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // _CHARS_PER_TOKEN)


def content_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.split()).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChunkDraft:
    chapter_ordinal: int
    text: str
    page_start: int
    page_end: int
    section: str | None
    content_hash: str


@dataclass(frozen=True)
class _Paragraph:
    page: int
    text: str


def chunk_document(
    document: ExtractedDocument, chapters: list[DetectedChapter]
) -> list[ChunkDraft]:
    resolved = _resolve_chapters(chapters, _page_count(document))
    drafts: list[ChunkDraft] = []
    sections = subsection_titles(document)
    for chapter in resolved:
        paragraphs = _chapter_paragraphs(document.pages, chapter)
        drafts.extend(_chunk_paragraphs(paragraphs, chapter.ordinal, sections))
    return drafts


def _page_count(document: ExtractedDocument) -> int:
    return max((page.ordinal for page in document.pages), default=0)


def _resolve_chapters(
    chapters: list[DetectedChapter], total_pages: int
) -> list[DetectedChapter]:
    ordered = sorted(chapters, key=lambda c: (c.page_start, c.ordinal))
    resolved: list[DetectedChapter] = []
    for index, chapter in enumerate(ordered):
        page_end = chapter.page_end
        if page_end is None:
            next_start = (
                ordered[index + 1].page_start - 1 if index + 1 < len(ordered) else None
            )
            page_end = (
                next_start if next_start is not None else max(total_pages, chapter.page_start)
            )
        resolved.append(
            DetectedChapter(
                ordinal=chapter.ordinal,
                title=chapter.title,
                page_start=chapter.page_start,
                page_end=page_end,
                source=chapter.source,
                confidence=chapter.confidence,
            )
        )
    return resolved


def _chapter_paragraphs(
    pages: list[ExtractedPage], chapter: DetectedChapter
) -> list[_Paragraph]:
    paragraphs: list[_Paragraph] = []
    for page in pages:
        if not (chapter.page_start <= page.ordinal <= (chapter.page_end or chapter.page_start)):
            continue
        for block in _split_page_text(page):
            paragraphs.append(_Paragraph(page=page.ordinal, text=block))
    return paragraphs


def _split_page_text(page: ExtractedPage) -> list[str]:
    text = page.text.strip()
    if not text:
        return []
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if len(blocks) <= 1:
        blocks = _sentence_groups(text)
    return blocks


def _sentence_groups(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.replace("\n", " "))
    groups: list[str] = []
    current: list[str] = []
    size = 0
    for sentence in sentences:
        current.append(sentence)
        size += len(sentence) + 1
        if size >= SENTENCE_GROUP_CHARS:
            groups.append(" ".join(current))
            current, size = [], 0
    if current:
        groups.append(" ".join(current))
    return groups


def _chunk_paragraphs(
    paragraphs: list[_Paragraph], chapter_ordinal: int, sections: list[tuple[int, str]]
) -> list[ChunkDraft]:
    drafts: list[ChunkDraft] = []
    buffer: list[_Paragraph] = []
    buffer_chars = 0

    def flush() -> None:
        nonlocal buffer, buffer_chars
        if not buffer:
            return
        text = "\n\n".join(p.text for p in buffer)
        page_start = buffer[0].page
        page_end = buffer[-1].page
        drafts.append(
            ChunkDraft(
                chapter_ordinal=chapter_ordinal,
                text=text,
                page_start=page_start,
                page_end=page_end,
                section=section_for_page(sections, page_start),
                content_hash=content_hash(text),
            )
        )
        buffer, buffer_chars = [], 0

    for paragraph in paragraphs:
        if buffer and paragraph.page - buffer[0].page >= MAX_PAGE_SPAN:
            flush()
        if buffer and buffer_chars + len(paragraph.text) > _MAX_CHARS:
            flush()
        if not buffer and len(paragraph.text) > _MAX_CHARS:
            for piece in _split_oversized(paragraph.text):
                buffer.append(_Paragraph(page=paragraph.page, text=piece))
                flush()
            continue
        buffer.append(paragraph)
        buffer_chars += len(paragraph.text)
        if buffer_chars >= _MIN_CHARS:
            flush()
    flush()
    return drafts


def _split_oversized(text: str) -> list[str]:
    pieces: list[str] = []
    for group in _sentence_groups(text):
        if len(group) <= _MAX_CHARS:
            pieces.append(group)
            continue
        start = 0
        while start < len(group):
            pieces.append(group[start : start + _MAX_CHARS].strip())
            start += _MAX_CHARS
    return [p for p in pieces if p]
