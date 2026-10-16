---
name: retro
description: Review a requested Sheet2Play session or phase for workflow, token-efficiency, and quality problems using recorded evidence. Use when the user asks for a retrospective or efficiency audit; do not run automatically after implementation.
license: MIT; see LICENSE
---

# Evidence-grounded retrospective

Adapted from [Matt Pocock's retro](https://github.com/mattpocock/skills/tree/main/skills/engineering/retro) for Sheet2Play.

Review the requested session, phase, or conversation range. If unspecified, use the current
session. Follow [AGENTS.md](../../../AGENTS.md) for repository constraints; reuse it if loaded.
A request to analyze authorizes analysis, not automatic edits, new rules, model changes,
delegation, or monitoring. Apply recommendations only when the user requests implementation.

## Gather enough evidence to explain the outcome

Inspect relevant commands, logs, handoffs, diffs, and verification results. Retrieve targeted
records rather than complete unrelated histories. State inaccessible or missing evidence;
do not invent usage numbers or attribute a failure to instructions without support.

Evaluate retrieval, execution, and quality together:

- Separate cached input, uncached input, and output. Reasoning is already part of output;
  do not double-count it. Cumulative tokens alone do not measure cost or subscription quota.
- Count useful roundtrips alongside empty polls, truncations, repeated reads, unchanged
  retries, failed preflights, unnecessary process launches, and abandoned work.
- Check whether acceptance criteria were met, regressions were caught, rework was needed,
  and any result remains unverified. Low token usage with a wrong result is not an improvement.
- Distinguish observed causes from plausible explanations. Compare comparable tasks where
  possible; differences in complexity, output size, caching, or interruptions can distort totals.

## Recommend changes proportional to the evidence

Prioritize the few changes most likely to reduce rework or wasted context. Prefer narrower
retrieval, shared authoritative pointers, filtered output, preflight checks, staged validation,
and completion notifications before changing model effort or adding agents.

For repeated mechanical failures, consider existing tests or deterministic checks. For
judgment failures, improve the relevant decision criteria rather than accumulating generic
rules. Keep implementation-critical standards available to the implementing agent; do not
move every standard into a review-only agent.

Report each material finding with its evidence, likely cause, proposed remedy, expected
tradeoff, and a way to verify improvement. Keep uncertain causal claims explicitly tentative.
Preserve required validation and scope boundaries. Recommend stronger reasoning or an
independent review only for a specific unresolved risk, not merely to hit a token target.

When edits are subsequently requested, use writing-for-agents for agent-facing documentation
if available; otherwise edit directly under the repository rules. Do not require another skill
or tool to complete this retrospective.
