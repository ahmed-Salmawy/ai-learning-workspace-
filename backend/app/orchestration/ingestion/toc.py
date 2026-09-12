import re
from dataclasses import dataclass

from app.orchestration.ingestion.extract import ExtractedDocument

_CHAPTER_PATTERN = re.compile(r"^\s*(chapter|part)\s+(\d+[a-z]?)\s*[:.\-—]?\s*(.*)$", re.IGNORECASE)


@dataclass(frozen=True)
class DetectedChapter:
    ordinal: int
    title: str
    page_start: int
    page_end: int | None
    source: str
    confidence: float


@dataclass(frozen=True)
class TOCDetection:
    chapters: list[DetectedChapter]
    source: str
    confidence: float


def detect_toc(document: ExtractedDocument) -> TOCDetection:
    from_toc = _from_embedded_toc(document)
    if from_toc is not None:
        return from_toc
    return _from_page_heuristics(document)


def _page_count(document: ExtractedDocument) -> int:
    return max((page.ordinal for page in document.pages), default=0)


def _from_embedded_toc(document: ExtractedDocument) -> TOCDetection | None:
    level_one = [entry for entry in document.toc if entry.level == 1]
    if len(level_one) < 2:
        return None
    total = _page_count(document)
    chapters: list[DetectedChapter] = []
    for index, entry in enumerate(level_one):
        page_start = entry.page
        page_end = level_one[index + 1].page - 1 if index + 1 < len(level_one) else total
        chapters.append(
            DetectedChapter(
                ordinal=index + 1,
                title=entry.title,
                page_start=page_start,
                page_end=page_end if page_end >= page_start else None,
                source="TOC",
                confidence=0.9,
            )
        )
    return TOCDetection(chapters=chapters, source="TOC", confidence=0.9)


def _from_page_heuristics(document: ExtractedDocument) -> TOCDetection:
    matches: list[tuple[int, str]] = []
    for page in document.pages:
        for line in page.text.splitlines():
            match = _CHAPTER_PATTERN.match(line)
            if match:
                number, title = match.group(2), (match.group(3) or "").strip()
                label = f"Chapter {number}" + (f": {title}" if title else "")
                if not matches or matches[-1][1] != label:
                    matches.append((page.ordinal, label))
    total = _page_count(document)
    chapters = [
        DetectedChapter(
            ordinal=index + 1,
            title=label,
            page_start=page,
            page_end=matches[index + 1][0] - 1 if index + 1 < len(matches) else total,
            source="INFERRED",
            confidence=0.5,
        )
        for index, (page, label) in enumerate(matches)
    ]
    return TOCDetection(chapters=chapters, source="INFERRED", confidence=0.5)


def section_for_page(entries: list[tuple[int, str]], page: int) -> str | None:
    best: tuple[int, str] | None = None
    for entry_page, title in entries:
        if entry_page <= page:
            best = (entry_page, title)
        else:
            break
    return best[1] if best else None


def subsection_titles(document: ExtractedDocument) -> list[tuple[int, str]]:
    return [(entry.page, entry.title) for entry in document.toc if entry.level >= 2]
