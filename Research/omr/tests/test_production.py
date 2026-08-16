from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest import mock

import pytest
from PIL import Image

from sheet2play_omr.errors import ResearchError
from sheet2play_omr.inference import PageInference
from sheet2play_omr.input_pages import PageInfo
from sheet2play_omr.production import predict_page_with_fallback


VALID_KERN = """**kern\t**kern
*M4/4\t*M4/4
=1\t=1
4c\t4C
*-\t*-
"""


def _page_result(mode: str) -> PageInference:
    return PageInference(
        page=1,
        total_pages=1,
        mode=mode,
        tokens=12,
        seconds=0.5,
        source_width=1050,
        source_height=1485,
        peak_vram_bytes=1024,
        appended_terminator=False,
        kern=VALID_KERN,
    )


@dataclass
class _FakeRunner:
    outcomes: list[Any]
    calls: list[str] = field(default_factory=list)

    def predict(self, image: Image.Image, *, page: int, total_pages: int, mode: str) -> PageInference:
        del image, page, total_pages
        self.calls.append(mode)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_beam_validation_failure_retries_with_grammar_on_same_runner() -> None:
    runner = _FakeRunner(
        [
            ResearchError("KERN_INVALID", "kern_validation", "bad beam", page=1),
            _page_result("grammar"),
        ]
    )
    progress: list[tuple[str, dict[str, Any]]] = []

    with mock.patch("sheet2play_omr.production._validate_page"):
        result, beam_error = predict_page_with_fallback(
            runner,  # type: ignore[arg-type]
            Image.new("RGB", (20, 20), "white"),
            PageInfo(1, 1, (20, 20)),
            progress_callback=lambda stage, **details: progress.append((stage, details)),
        )

    assert runner.calls == ["beam", "grammar"]
    assert result.mode == "grammar"
    assert beam_error is not None and beam_error.code == "KERN_INVALID"
    assert [stage for stage, _ in progress] == ["page_retry"]


@pytest.mark.parametrize(
    "code",
    ("CUDA_OUT_OF_MEMORY", "MODEL_INVALID", "CUDA_UNAVAILABLE", "INFERENCE_FAILED"),
)
def test_non_recognition_failures_never_retry(code: str) -> None:
    runner = _FakeRunner([ResearchError(code, "inference", "fatal", page=1)])

    with pytest.raises(ResearchError) as raised:
        predict_page_with_fallback(
            runner,  # type: ignore[arg-type]
            Image.new("RGB", (20, 20), "white"),
            PageInfo(1, 1, (20, 20)),
        )

    assert raised.value.code == code
    assert runner.calls == ["beam"]


def test_dual_decoder_failure_preserves_both_diagnostics() -> None:
    runner = _FakeRunner(
        [
            ResearchError("KERN_INVALID", "kern_validation", "beam fields", page=2),
            ResearchError("KERN_PARSE_FAILED", "symbolic_parse", "grammar rhythm", page=2),
        ]
    )

    with pytest.raises(ResearchError) as raised:
        predict_page_with_fallback(
            runner,  # type: ignore[arg-type]
            Image.new("RGB", (20, 20), "white"),
            PageInfo(2, 3, (20, 20)),
        )

    assert raised.value.code == "KERN_PARSE_FAILED"
    assert raised.value.page == 2
    assert "beam fields" in str(raised.value)
    assert "grammar rhythm" in str(raised.value)
    assert runner.calls == ["beam", "grammar"]
