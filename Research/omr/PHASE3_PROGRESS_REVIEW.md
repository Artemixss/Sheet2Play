# Phase 3 progress and deferred-candidate review

> **Historical review, superseded 2026-09-26.** The selected
> [screening comparison plan](COMPARISON_PLAN.md) replaces the recommendation
> below to finish the old exhaustive sequence first.

Review date: 2026-09-25, approximately 23:56 Europe/Istanbul.

**Recommendation: finish the current reduced evaluation through a checked resume, then evaluate fine-tuned HOMR and add ready challengers in a separately versioned extension. Do not describe the reduced roster as the final search for the best OMR engine.**

This is a review, not a restart, inference request, plan amendment, or authorization for training/cloud spending. No workers were launched or stopped. Read with the [active handoff](PHASE3_HANDOFF.md), [canonical plan](COMPARISON_PLAN.md), and [readiness review](PHASE3_READINESS_REVIEW.md).

## Actual status versus the handoff

The handoff's statement that frozen inference has not started is now historical. The live records show:

- Primary SMB reference audit finished with **402 valid, zero invalid**.
- Bootstrap created `phase3-config-freeze-v1-89f385c8790b.json`, SHA-256 `3fdd3d76aeab4188244795ea7b5eb310b2129d8d50131290297aeb1a32020633`.
- All seven frozen one-item entry commands completed. This means the commands completed under the failure policy, not that all predictions were accurate or necessarily accepted.
- Sequence stage 1, primary HOMR inference, logged progress through **item 76/402**. This is progress, not an accuracy result or a count of successful predictions.
- Secondary reference audit last logged **item 432/611**; no completed secondary-audit gate was established by this review.
- The state file still marks stage 1 `running`, but a read-only process inventory found no matching Phase 3 bootstrap, sequence, inference, or reference-audit worker, and none of the recorded worker PIDs remained active. The jobs appear interrupted. The cause was not established; empty inference stderr does not prove clean completion.

Do not simply launch another bootstrap. The sequence intentionally refuses a stale `running` stage and existing logs. The executor should verify freeze/source/runtime identities and saved item artifacts, preserve the old logs, reconcile the interrupted stage, then resume only unfinished work. Resume the secondary reference audit with the same identity and keep its gate before secondary inference. An incomplete candidate attempt must not be mistaken for a completed cached result.

## Review findings

The previous Zeus entry concern has materially improved: the runner now uses stable part IDs, and its note-bearing test passes through the runner and shared normalization with swapped part order, pickup timing, and a cross-system tie. A changed part identity is rejected. I reran the Zeus-runner, Phase 3 reference, and Phase 3 scoring test files: **16 tests passed**. This was targeted validation, not an independent rerun of the handoff's complete 115-test suite or a full audit of all frozen predictions.

The preparation separates reference validation from candidate output and freezes settings before evaluation. Those are reasons to continue. Operational interruption and stale documentation require recovery, not a new scientific plan. Do not tune the active candidates against the now-started frozen evaluation.

The private diagnostic still lacks a verified page-level timing split. Its pitch-count check cannot validate rhythm or support the primary ranking. Primary SMB, overlapping secondary SMB, and OLiMPiC must remain distinct evidence tracks; the secondary collection is not an independent replication of the primary collection.

## Why the missing candidates are actually missing

| Candidate | Established blocker | Sensible next step |
| --- | --- | --- |
| Rokot Q8 | It already runs on the local GPU. Ten of twelve generated controls produced accepted output, but zero of twenty corrected open pages did. Recognition truncation, strict conversion, and voice/state/lyric joining limitations are mixed. | A bounded development investigation comparing individual-system recognition with page assembly. Fix demonstrated adapter defects, validate a complete page, then freeze a new configuration. Do not treat accepted crops as accurate transcriptions. |
| Vanilla Qwen | It also runs locally. All twelve generated controls failed, and the corrected-page sanity still emitted invalid ABC. | Lower-priority, narrowly specified inference/format sanity work if revisited. More VRAM alone is not an evidenced remedy. Do not fold an unbounded prompt search into the active run. |
| LEGATO | Recognition runtime and weights are unprovisioned; 6 GB feasibility is unknown, not disproved. It uses the external vision encoder plus its dedicated decoder. | Assess the exact pinned configuration, dtype, loading transients and activations, then measure a development inference if feasible. Any cloud fallback needs a cost estimate within the existing total cap. |
| HOMR PR #156 | Compatible recognition weights have not been verified. | Resolve checkpoint availability and architecture/tokenizer compatibility before resource provisioning. |
| MuSViT | No usable recognition decoder/checkpoint has been established in the project review. | Verify whether a complete inference path is available; otherwise define separately authorized training research with faithful labels, evaluation, compute budget and this project's generator. |

These are different readiness problems. Calling all five “too large for 6 GB” would lead to the wrong next investment. More GPU memory does not fix malformed notation, a missing decoder, or absent compatible weights.

## What the current comparison can still answer

Past poor application experiences are evidence worth investigating, not a controlled ranking. The corrected Zeus research pipeline also differs from the old app path. This round can quantify HOMR's rhythm deficit, whether Audiveris trades pitch accuracy for better timing, whether corrected Zeus changes the earlier picture, and where failures occur. Even if HOMR wins every comparison, its measured weaknesses become a useful target for later challengers.

It cannot establish that HOMR is better than untested Rokot or LEGATO, or settle the expanded engine search. The result should be labeled a baseline comparison of the evaluated configurations.

## Possible outcomes and decisions

| Observed outcome after complete evaluation | Decision it supports |
| --- | --- |
| HOMR beats Audiveris and Zeus across relevant metrics | Retain it while evaluating the fine-tune and preparing later challengers. No conclusion about deferred models. |
| Audiveris has better rhythm but worse pitch/coverage | Inspect the tradeoff; do not automatically replace HOMR or assume a hybrid system will work. Any hybrid is a new evaluated pipeline. |
| Corrected Zeus improves substantially | Investigate the integration explanation and compare the complete configuration against fine-tuned HOMR before considering promotion. |
| Fine-tuning improves pitch but leaves onset/duration weak | Stop assuming that more of the same training will fix rhythm. Use development diagnostics to distinguish representation loss, recognition, and conversion/integration defects. |
| Rokot later has strong system recognition but weak page output | Prioritize demonstrated assembly defects; require end-to-end validation before judging application suitability. |
| A later challenger beats fine-tuned HOMR | Apply the unchanged paired/statistical and practical promotion gate, then request a separate opt-in integration phase. |

These are conditional branches, not predictions of the ranking. A close or uncertain result supports retaining the existing engine pending stronger evidence.

## Recommended sequence

1. **Finish Phase 3:** recover the interrupted jobs, preserve cached outputs only when identities and hashes match, and complete the frozen reduced comparison.
2. **Phase 4:** verify the supplied HOMR fine-tune checkpoint and training provenance, select on development data, and evaluate it using the same protocol. Do not restart training.
3. **Propose a versioned challenger extension:** prioritize Rokot development readiness and LEGATO feasibility, with a smaller Qwen investigation; keep PR #156 and MuSViT conditional. This preserves the user's original expanded objective without disrupting current measurements. It needs an explicit scope decision before execution.
4. **Phase 5:** perform paired analysis and recommendations for the evaluated configurations. If the challenger extension is pending, clearly label the first recommendation as restricted to the current roster; refresh it when valid challenger results arrive.

Later models can use the same frozen inputs and scoring, with matching baseline evidence reused where identities remain compatible. Tune only on development data, pin new configurations before evaluation, disclose training overlap and all attempted comparisons, and update the multiple-comparison accounting for the expanded claims. Do not use inspected benchmark errors to iteratively tune challengers and still call the result untouched validation.

**Decision for the user:** proceed with completion of the current evaluation, not directly to a replacement decision. Keep Rokot and LEGATO explicitly on the roadmap. No new broad model search or training is required to recover the current run.
