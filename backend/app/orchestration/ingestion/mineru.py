import json
import logging
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.orchestration.ingestion.extract import (
    ExtractedDocument,
    ExtractedPage,
    TOCEntry,
)

logger = logging.getLogger(__name__)


class MinerUError(RuntimeError):
    pass


class MinerUCliDocumentConverter:
    """Drive the `mineru` CLI (separate Python 3.10-3.13 env) and convert its
    output into an ExtractedDocument with page-level provenance.

    MinerU keeps the PDF's real page assignment per content block, removes
    headers/footers/page numbers, preserves heading hierarchy, and converts
    tables to HTML and formulas to LaTeX.
    """

    def __init__(
        self,
        command: str = "mineru",
        backend: str = "pipeline",
        timeout_seconds: float = 3600.0,
        runner: Any | None = None,
    ) -> None:
        self._command = command
        self._backend = backend
        self._timeout = timeout_seconds
        self._runner = runner or subprocess.run

    @property
    def model(self) -> str:
        return f"mineru-cli/{self._backend}"

    def extract(self, data: bytes) -> ExtractedDocument:
        with tempfile.TemporaryDirectory(prefix="mineru-") as tmp:
            workdir = Path(tmp)
            input_path = workdir / "input.pdf"
            input_path.write_bytes(data)
            output_dir = workdir / "output"
            output_dir.mkdir()

            self._run_cli(input_path, output_dir)

            content_list_path = self._find(output_dir, "*_content_list.json")
            if content_list_path is None:
                raise MinerUError(
                    "mineru produced no *_content_list.json; cannot preserve "
                    "page provenance"
                )
            blocks = json.loads(content_list_path.read_text(encoding="utf-8"))
            title = self._guess_title(output_dir, blocks)
            return self._to_document(blocks, title)

    def _run_cli(self, input_path: Path, output_dir: Path) -> None:
        command = [
            self._command,
            "-p",
            str(input_path),
            "-o",
            str(output_dir),
            "-b",
            self._backend,
        ]
        logger.info("running mineru: %s", " ".join(command))
        try:
            result = self._runner(command, capture_output=True, timeout=self._timeout)
        except subprocess.TimeoutExpired as exc:
            raise MinerUError(f"mineru timed out after {self._timeout}s") from exc
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")[-1000:]
            raise MinerUError(f"mineru failed (code {result.returncode}): {stderr}")

    def _find(self, output_dir: Path, pattern: str) -> Path | None:
        matches = sorted(output_dir.rglob(pattern))
        return matches[0] if matches else None

    def _guess_title(self, output_dir: Path, blocks: list[dict]) -> str | None:
        middle = self._find(output_dir, "*_middle.json")
        if middle is not None:
            try:
                meta = json.loads(middle.read_text(encoding="utf-8"))
                pdf_meta = meta.get("pdf_meta", {})
                if pdf_meta.get("title"):
                    return str(pdf_meta["title"])
            except (json.JSONDecodeError, OSError):
                pass
        for block in blocks:
            if block.get("text_level") == 1 and block.get("text"):
                return str(block["text"])
        return None

    def _to_document(self, blocks: list[dict], title: str | None) -> ExtractedDocument:
        page_texts: dict[int, list[str]] = defaultdict(list)
        toc: list[TOCEntry] = []
        for block in blocks:
            page = int(block.get("page_idx", 0)) + 1
            block_type = block.get("type", "text")
            text = self._block_text(block, block_type)
            if text:
                page_texts[page].append(text)
            level = block.get("text_level")
            if level and block.get("text") and block_type == "text":
                toc.append(
                    TOCEntry(
                        level=int(level),
                        title=str(block["text"]).strip(),
                        page=page,
                    )
                )
        if not page_texts and blocks:
            page_texts[1].append("")
        pages = [
            ExtractedPage(ordinal=page, text="\n\n".join(page_texts[page]))
            for page in sorted(page_texts)
        ]
        return ExtractedDocument(pages=pages, title=title, toc=toc)

    def _block_text(self, block: dict, block_type: str) -> str | None:
        if block_type == "text":
            return str(block.get("text", "")).strip() or None
        if block_type == "table":
            body = block.get("table_body")
            caption = block.get("table_caption")
            parts: list[str] = []
            if caption:
                parts.append(" ".join(str(c) for c in caption))
            if body:
                parts.append(str(body))
            return "\n".join(parts).strip() or None
        if block_type == "equation":
            return str(block.get("text", "")).strip() or None
        if block_type == "image":
            caption = block.get("img_caption")
            if caption:
                return "[figure] " + " ".join(str(c) for c in caption)
            return None
        return None
