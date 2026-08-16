"""
Sheet2Play research adapter: rhythm-aware constrained decoding (Step 4).

Extends the grammar decoder by injecting RhythmRule from the pinned
Transcoda source into the StatefulKernLogitsProcessor constraint stack.

RhythmRule is fully implemented in the pinned Transcoda source but
deliberately disabled in the shared ConstrainedDecodingFactory (see
constraint_factory.py lines 126-128). This adapter enables it without
modifying the pinned Transcoda checkout.

Policy version: rhythm-aware-v1

Constraints honoured:
- Fresh RhythmRule state per generation call.
- 60-second deadline per generation (inherited from TranscodaRunner).
- CUDA-only inference (inherited).
- Deterministic greedy decoding (inherited).
- No decoded-token repair after generation.
- Fails if the constraint cannot represent a legal continuation.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Any

from .errors import ResearchError
from .inference import (
    GRAMMAR_TIMEOUT_SECONDS,
    _DeadlineStoppingCriteria,
    TranscodaRunner,
)

# ---------------------------------------------------------------------------
# Policy fingerprint
# The policy string uniquely identifies this decoder configuration.
# Any change to constraints, timeout, or preprocessing must bump the version.
# ---------------------------------------------------------------------------

RHYTHM_POLICY_ID = (
    "cuda|1485x1050|300dpi|grammar-rhythm-aware-v1|max2048"
    "|grammar-timeout60s|numeric-tempo-or-120"
)
# Short hash for cache keys and checkpoint labels
RHYTHM_POLICY_HASH: str = hashlib.sha256(RHYTHM_POLICY_ID.encode()).hexdigest()[:16]
RHYTHM_POLICY_VERSION = "rhythm-aware-v1"


class RhythmAwareTranscodaRunner(TranscodaRunner):
    """Grammar decoder with RhythmRule injected into the constraint stack.

    The pinned ConstrainedDecodingFactory deliberately stores
    ``use_rhythm_constraints`` as a backward-compatible flag only and never
    attaches ``RhythmRule`` to the logits-processor chain. This subclass
    overrides ``_new_grammar_bundle()`` to inject it after the bundle is
    constructed by the parent, without touching the pinned Transcoda source.

    The injection rebuilds the ``StatefulKernLogitsProcessor`` with
    ``RhythmRule`` appended to its ``rule_factories`` list so that a fresh
    ``RhythmRule`` instance is created for every generation call. The
    ``RhythmRule`` is also appended to ``semantic_rule_factories`` so that
    the post-generation semantic finalizer can validate rhythm at sequence
    end.
    """

    def _new_grammar_bundle(self) -> tuple[Any, _DeadlineStoppingCriteria]:
        # Build the standard bundle (GBNF + interpretation + spine + deadline)
        bundle, deadline = super()._new_grammar_bundle()

        try:
            from src.grammar.rhythm_rule import RhythmRule
            from src.grammar.stateful_kern_logits_processor import (
                StatefulKernLogitsProcessor,
            )
        except ImportError as error:
            raise ResearchError(
                "GRAMMAR_INITIALIZATION_FAILED",
                "inference",
                f"Cannot import RhythmRule from pinned Transcoda source: {error}",
            ) from error

        # Rebuild StatefulKernLogitsProcessor with RhythmRule appended.
        # We scan by type rather than position so this survives reordering.
        new_processors: list[Any] = []
        rhythm_injected = False

        for processor in bundle.logits_processors or []:
            if isinstance(processor, StatefulKernLogitsProcessor):
                if rhythm_injected:
                    # Should never happen with the current factory, but be safe.
                    new_processors.append(processor)
                    continue
                extended_factories = list(processor._rule_factories) + [RhythmRule]
                new_processor = StatefulKernLogitsProcessor(
                    i2w=self.i2w,
                    bos_token_id=self.model.config.bos_token_id,
                    eos_token_id=self.model.config.eos_token_id,
                    pad_token_id=self.tokenizer.pad_token_id,
                    rule_factories=extended_factories,
                )
                new_processors.append(new_processor)
                rhythm_injected = True
            else:
                new_processors.append(processor)

        if not rhythm_injected:
            # No StatefulKernLogitsProcessor was in the bundle (possible if
            # grammar_provider is None or if factory changes). Add one with
            # only RhythmRule so the experiment still runs.
            new_processors.append(
                StatefulKernLogitsProcessor(
                    i2w=self.i2w,
                    bos_token_id=self.model.config.bos_token_id,
                    eos_token_id=self.model.config.eos_token_id,
                    pad_token_id=self.tokenizer.pad_token_id,
                    rule_factories=[RhythmRule],
                )
            )

        # Append RhythmRule to semantic_rule_factories so the post-generation
        # finalizer also validates rhythm when deciding whether to append
        # a spine terminator.
        new_semantic_factories = tuple(bundle.semantic_rule_factories) + (RhythmRule,)

        new_bundle = replace(
            bundle,
            logits_processors=new_processors,
            semantic_rule_factories=new_semantic_factories,
        )
        return new_bundle, deadline
