from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ExtractedPage:
    ordinal: int
    text: str


@dataclass(frozen=True)
class TOCEntry:
    level: int
    title: str
    page: int


@dataclass(frozen=True)
class ExtractedDocument:
    pages: list[ExtractedPage]
    title: str | None = None
    author: str | None = None
    toc: list[TOCEntry] = field(default_factory=list)


class TextExtractor(Protocol):
    def extract(self, data: bytes) -> ExtractedDocument: ...
