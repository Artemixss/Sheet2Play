---
name: writing-for-agents
description: Create or revise agent-facing guidance, startup context, skills, and phase handoffs in Sheet2Play. Use for documentation that directs agent work, not ordinary application implementation or user-facing prose.
license: MIT; see LICENSE
---

# Writing for agents

Adapted from [Matt Pocock's writing-for-agents](https://github.com/mattpocock/skills/tree/main/skills/productivity/writing-for-agents) for Sheet2Play.

## Find the authority and the reader's next decision

Use the already-loaded repository instructions. If unavailable, read
[AGENTS.md](../../../AGENTS.md); its "Where to look" table names the owning document for
each task. Follow only the links needed for the requested edit; do not inventory every
Markdown file.

Identify what an arriving agent must decide or do, which source owns the answer, and what
evidence supports it. An unverified assumption stays labelled as an assumption. The latest
user decision governs scope; surface material conflicts before writing dependent guidance.

## Keep instructions near their use

- Keep shared repository rules in AGENTS.md; CLAUDE.md points there. Put task-specific
  detail in the relevant plan or handoff rather than duplicating it in root instructions.
- A context pointer states what the linked source contains and when to consult it.
  Inline short information needed on every path; link substantial conditional detail.
- State concrete prerequisites, deliverables, acceptance evidence, and stop/replanning
  conditions. Avoid vague instructions such as "be thorough" or "verify everything".
- Describe the current state once and separate it from dated history. Mark obsolete
  proposals superseded and link their replacement; preserve useful experimental evidence,
  frozen contracts, historical manifests, and licenses.
- A handoff supplements its canonical plan with completed work, evidence, deviations,
  unresolved questions, and the next authorized action. For interrupted jobs, retain
  identity, logs, resumable progress, and the instruction to check for a live worker.

## Make the smallest useful revision

Remove duplication and instructions that do not change a decision. Preserve operational
constraints that protect data, evaluation validity, resource limits, authorization, or
release correctness. Do not transplant another tool's invocation syntax or unavailable
agent/tool commands into Codex instructions.

Prefer an existing deterministic check for a recurring mechanical invariant. Propose new
automation only when supported by the task; a documentation request does not authorize a
new workflow, repository-wide rewrite, or runtime change.

Check changed relative links and scoped searches. Explain which source is authoritative
and flag remaining uncertainty; do not present historical statements as current work orders.
