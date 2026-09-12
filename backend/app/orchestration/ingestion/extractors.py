import pymupdf

from app.orchestration.ingestion.extract import ExtractedDocument, ExtractedPage, TOCEntry


class PyMuPDFTextExtractor:
    def extract(self, data: bytes) -> ExtractedDocument:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            pages = [
                ExtractedPage(ordinal=page.number + 1, text=page.get_text("text"))
                for page in doc
            ]
            metadata = doc.metadata or {}
            toc = [
                TOCEntry(level=int(level), title=str(title).strip(), page=int(page))
                for level, title, page in doc.get_toc(simple=True)
                if page > 0
            ]
            return ExtractedDocument(
                pages=pages,
                title=metadata.get("title") or None,
                author=metadata.get("author") or None,
                toc=toc,
            )


class PlainTextExtractor:
    def extract(self, data: bytes) -> ExtractedDocument:
        text = data.decode("utf-8", errors="replace")
        return ExtractedDocument(pages=[ExtractedPage(ordinal=1, text=text)])
