import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from app.orchestration.ingestion.extract import TextExtractor
from app.orchestration.ingestion.mineru import MinerUCliDocumentConverter, MinerUError

CONTENT_LIST = [
    {"type": "text", "text": "Chapter 1: Getting Started", "text_level": 1, "page_idx": 0},
    {"type": "text", "text": "This paragraph explains retrieval pipelines.", "page_idx": 0},
    {"type": "equation", "text": "$E = mc^2$", "page_idx": 0},
    {
        "type": "table",
        "table_body": "<table><tr><td>a</td></tr></table>",
        "table_caption": ["Table 1: results"],
        "page_idx": 1,
    },
    {
        "type": "image",
        "img_path": "images/fig1.jpg",
        "img_caption": ["Figure 1: flow"],
        "page_idx": 1,
    },
    {"type": "text", "text": "Chapter 2: Going Deeper", "text_level": 1, "page_idx": 2},
    {"type": "text", "text": "Deeper content paragraph.", "page_idx": 2},
]


def _fake_runner_factory(
    output_files: dict[str, bytes], returncode: int = 0
) -> Callable[..., subprocess.CompletedProcess]:
    def fake_runner(
        command: list[str], capture_output: bool = True, timeout: float | None = None
    ) -> subprocess.CompletedProcess:
        out_index = command.index("-o")
        output_dir = Path(command[out_index + 1])
        for rel, content in output_files.items():
            target = output_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        return subprocess.CompletedProcess(command, returncode, b"", b"")

    return fake_runner


def _expected_files() -> dict[str, bytes]:
    return {
        "input/auto/input_content_list.json": json.dumps(CONTENT_LIST).encode("utf-8"),
        "input/auto/input_middle.json": json.dumps(
            {"pdf_meta": {"title": "A Test Book"}}
        ).encode("utf-8"),
    }


def test_satisfies_text_extractor_protocol() -> None:
    converter: TextExtractor = MinerUCliDocumentConverter(
        runner=_fake_runner_factory(_expected_files())
    )
    assert converter is not None


def test_extracts_pages_with_provenance_and_headings() -> None:
    converter = MinerUCliDocumentConverter(runner=_fake_runner_factory(_expected_files()))

    document = converter.extract(b"%PDF-fake")

    assert [p.ordinal for p in document.pages] == [1, 2, 3]
    assert "retrieval pipelines" in document.pages[0].text
    assert "$E = mc^2$" in document.pages[0].text
    assert "Table 1: results" in document.pages[1].text
    assert "[figure] Figure 1: flow" in document.pages[1].text
    assert document.title == "A Test Book"
    assert [(e.level, e.title, e.page) for e in document.toc] == [
        (1, "Chapter 1: Getting Started", 1),
        (1, "Chapter 2: Going Deeper", 3),
    ]


def test_cli_invocation_uses_pipeline_backend(tmp_path: Path) -> None:
    captured: dict = {}

    def runner(
        command: list[str], capture_output: bool = True, timeout: float | None = None
    ) -> subprocess.CompletedProcess:
        captured["command"] = command
        captured["timeout"] = timeout
        out_index = command.index("-o")
        output_dir = Path(command[out_index + 1])
        target = output_dir / "input" / "auto" / "input_content_list.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(json.dumps(CONTENT_LIST).encode())
        return subprocess.CompletedProcess(command, 0, b"", b"")

    converter = MinerUCliDocumentConverter(
        command="mineru313", backend="pipeline", timeout_seconds=99, runner=runner
    )
    converter.extract(b"%PDF-fake")

    assert captured["command"][:4] == ["mineru313", "-p", str(captured["command"][2]), "-o"]
    assert "-b" in captured["command"]
    assert captured["command"][captured["command"].index("-b") + 1] == "pipeline"
    assert captured["timeout"] == 99


def test_nonzero_exit_raises(tmp_path: Path) -> None:
    def failing_runner(
        command: list[str], capture_output: bool = True, timeout: float | None = None
    ) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(command, 1, b"", b"model load failed")

    converter = MinerUCliDocumentConverter(runner=failing_runner)

    with pytest.raises(MinerUError, match="model load failed"):
        converter.extract(b"%PDF-fake")


def test_timeout_raises(tmp_path: Path) -> None:
    def slow_runner(
        command: list[str], capture_output: bool = True, timeout: float | None = None
    ) -> subprocess.CompletedProcess:
        raise subprocess.TimeoutExpired(cmd=command, timeout=timeout or 0)

    converter = MinerUCliDocumentConverter(runner=slow_runner, timeout_seconds=5)

    with pytest.raises(MinerUError, match="timed out"):
        converter.extract(b"%PDF-fake")


def test_missing_content_list_raises(tmp_path: Path) -> None:
    converter = MinerUCliDocumentConverter(runner=_fake_runner_factory({}))

    with pytest.raises(MinerUError, match="content_list"):
        converter.extract(b"%PDF-fake")
