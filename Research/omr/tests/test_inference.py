from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest import mock

import pytest

from sheet2play_omr.errors import ResearchError
from sheet2play_omr.inference import (
    GRAMMAR_MASK_BACKEND,
    TranscodaRunner,
    _DeadlineStoppingCriteria,
    _XGrammarBackendAdapter,
    _require_safe_finalization,
)


@dataclass
class _FakeXGrammar:
    marker: str = "delegated"
    calls: list[tuple[Any, Any, str]] = field(default_factory=list)

    def apply_token_bitmask_inplace(self, logits: Any, bitmask: Any, *, backend: str) -> None:
        self.calls.append((logits, bitmask, backend))


@dataclass(frozen=True)
class _Finalization:
    text: str
    appended_terminator: bool = False
    trimmed_incomplete_tail: bool = False
    truncated: bool = False


@dataclass(frozen=True)
class _Bundle:
    logits_processors: list[Any] | None = None
    stopping_criteria: list[Any] | None = None
    semantic_rule_factories: tuple[Any, ...] = ()


def test_xgrammar_adapter_uses_portable_cuda_backend() -> None:
    module = _FakeXGrammar()
    adapter = _XGrammarBackendAdapter(module)

    adapter.apply_token_bitmask_inplace("logits", "bitmask")

    assert GRAMMAR_MASK_BACKEND == "torch_native"
    assert module.calls == [("logits", "bitmask", "torch_native")]
    assert adapter.marker == "delegated"


def test_grammar_runtime_is_initialized_once_but_bundle_state_is_fresh() -> None:
    runner = object.__new__(TranscodaRunner)
    runner._grammar_runtime = None
    runner.device_name = "NVIDIA GeForce RTX 4050 Laptop GPU"
    runner._progress = lambda stage, **details: None
    runner.runtime_metadata = {"grammar_mask_backend": None}
    first_bundle = _Bundle(logits_processors=[])
    second_bundle = _Bundle(logits_processors=[])
    factory = mock.Mock()
    factory.build.side_effect = (first_bundle, second_bundle)
    runtime = (factory, object())

    with mock.patch.object(
        TranscodaRunner,
        "_load_grammar_runtime",
        return_value=runtime,
    ) as load:
        first_runtime = runner._ensure_grammar_runtime()
        second_runtime = runner._ensure_grammar_runtime()
        first = runner._new_grammar_bundle()
        second = runner._new_grammar_bundle()

    assert first_runtime is runtime
    assert second_runtime is runtime
    first_built, first_deadline = first
    second_built, second_deadline = second
    assert first_built.logits_processors == first_bundle.logits_processors
    assert second_built.logits_processors == second_bundle.logits_processors
    assert first_deadline in first_built.stopping_criteria
    assert second_deadline in second_built.stopping_criteria
    assert first is not second
    assert runner.runtime_metadata["grammar_mask_backend"] == GRAMMAR_MASK_BACKEND
    load.assert_called_once_with()
    assert factory.build.call_count == 2


def test_grammar_deadline_stops_generation() -> None:
    deadline = _DeadlineStoppingCriteria(0.0)

    assert deadline(None, None)
    assert deadline.timed_out


def test_safe_finalization_accepts_only_a_terminator_record() -> None:
    raw = "*clefG2\t*clefF4\n4c\t4C\n"
    finalized = _Finalization(text=raw + "*-\t*-", appended_terminator=True)

    assert _require_safe_finalization(raw, finalized, page=1) == finalized.text


@pytest.mark.parametrize(
    "finalized",
    (
        _Finalization(text="4d\t4D\n*-\t*-", appended_terminator=True),
        _Finalization(text="4c\t4C\n*^\t*", appended_terminator=True),
        _Finalization(text="4c\t4C\n*-\t*-", trimmed_incomplete_tail=True),
        _Finalization(text="4c\t4C\n*-\t*-", truncated=True),
    ),
)
def test_safe_finalization_rejects_content_repairs_and_truncation(finalized: _Finalization) -> None:
    with pytest.raises(ResearchError):
        _require_safe_finalization("4c\t4C\n", finalized, page=2)
