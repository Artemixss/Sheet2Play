# Phase 3 readiness decision after the Phase 2R correction

Date: 2026-09-25

**Recommendation: conditional GO for a reduced Phase 3 roster, not the full expanded comparison. Accept the coordinate correction. Move into configuration freeze and development-only entry checks, then evaluate only configurations that pass. Do not keep the whole comparison waiting for Rokot, Qwen, or LEGATO.**

This review does not start or authorize evaluation. The user requested analysis and a report. The [canonical plan](COMPARISON_PLAN.md) remains authoritative; the [correction handoff](PHASE2R_CORRECTION_HANDOFF.md) records execution. Fine-tuned HOMR remains the later approval baseline, and Phase 3 cannot establish a final replacement recommendation.

## Evidence independently checked

- Read the correction implementation, relevant tests, reports, and the plan's separation of recognition, conversion, joining, and app integration.
- Reran `test_phase2r.py`, `test_phase2_zeus_runner.py`, and `test_phase2.py`: **29 tests passed**, including the Phase-1 freeze check and evaluation fixtures. The handoff's full 101-test research run and bridge suite were not independently rerun in this review.
- Verified the corrected Rokot aggregate's 32 per-item report hashes. Across the correction evidence, checked **36 reports and 278 declared artifacts: zero missing files or hash mismatches**.
- Verified that the current detector and VLM implementation hashes match the handoff.
- Inspected the corrected representative first crop: both piano staves are present. The implementation crops the saved detector-returned image, verifies its hash/dimensions, and rejects the wrong coordinate space or source identity. Regression coverage exercises combined resize/autocrop transformations. This closes the specific original coordinate defect; it does not prove perfect segmentation on every score.

No new model inference, training, benchmark execution, downloads, spending, or runtime edits were performed for this review.

## What the correction establishes

The original reason to block all progress has been resolved. The saved image used for recognition now matches the coordinate space of the detector boxes. Old page trials remain historical evidence of the defective pipeline and must not be reused as model-only results.

Rokot's corrected results are nevertheless insufficient for complete-page evaluation: **10/12 generated controls accepted, 0/20 open first pages accepted**. Of 81 detected systems, the handoff records 61 extracted ABC outputs, 34 strict per-system conversion successes, 27 conversion failures, and 20 systems without ABC after early stopping. Page joins also reject lyrics, inconsistent voice identities, and musical-state differences. These counts identify a mixture of recognition and adapter limitations; they do not show that Rokot is intrinsically worse than HOMR. Preserving it for a future bounded adapter investigation is reasonable, but repeatedly extending readiness work is not required before measuring other engines.

Qwen failed its corrected-page sanity check as well as all 12 historical generated controls, which bypass page cropping. Deprioritizing the tested configuration is justified without another full prompt search.

Audiveris has a genuine native-page route and 20 accepted open first pages. Its `<divisions>0` export explains the reproduced normalization exception. Count such failures under the frozen policy; do not repair them from ground truth. A poor prediction is a valid benchmark outcome when the adapter faithfully preserves it.

LEGATO's revised status is appropriate: unprovisioned and unmeasured, not proven impossible on 6 GB. It need not block this evaluation round. Its default-config parameter estimate is not a measured resource result for the pinned checkpoint.

## Recommended roster

| Configuration | Decision for Phase 3 |
| --- | --- |
| Shipped HOMR | Mandatory control. Carry forward verified identity; confirm a complete-page development path before frozen page inference. Historical crop success alone is not page coverage. |
| Audiveris native page path | Include after ordinary configuration/runtime freeze. Retain all failures and invalid exports in denominators. |
| Zeus neutral corrected page runner | Conditional inclusion after the join-preservation check below. One successful page proves execution, not general timing correctness. Label it as the research page pipeline. |
| Zeus upstream annotated-system path | Include in the compatible system-level track. Never merge its results into the complete-page ranking. |
| Zeus direct research-engine/app extraction path | Withhold from the ready page roster. Retain its measured failure as integration evidence; do not substitute neutral-runner success for this path. |
| Rokot Q8 complete-page path | Defer the current configuration because no complete-page development route succeeds. Preserve crop evidence separately; no permanent model rejection. |
| Vanilla Qwen current configuration | Defer after the bounded failed sanity check. |
| LEGATO / HOMR PR #156 / MuSViT | Unavailable or conditional, not zero-scored candidates. MuSViT training remains separate. |
| Fine-tuned HOMR | Phase 4 checkpoint verification/selection and evaluation, then Phase 5 replacement analysis. Do not restart training or move this evaluation into Phase 3. |

This is a reduced comparison, not completion of the user's original eight-to-nine-entry ambition. The final report must explicitly identify omitted configurations and cannot claim to have found the best engine across the full proposed roster.

## Entry checks before frozen inference

1. **Record the reduced roster and freeze exact configurations.** Pin loaded weights, sources and patches, preprocessors, conversion/normalization behavior, limits, and failure handling. Record excluded/unavailable entries and training-overlap disclosures in a versioned sidecar without changing frozen manifests. Recheck runtime identity and input hashes at launch.

2. **Verify page readiness for the mandatory control and musical preservation for Zeus.** Reuse matching prior evidence where it exists. Otherwise perform development-only checks. The reviewed Zeus `_stitch` appends measures by part position and checks part count; its dedicated join test uses empty measures and only checks measure numbers. This does not establish the plan's preservation of part identity, ties, inherited state, and pickup timing. Exercise actual note-bearing, multi-system fixtures through this runner and shared normalization, including voice/part order and a cross-system tie. Compare exact canonical events with known fixture truth. A failure blocks this Zeus configuration, not Audiveris or HOMR. Do not invent an implementation defect merely because coverage is missing.

3. **Resolve interpretation, not necessarily every bad prediction.** The direct Zeus extractor rejects an overfull measure while shared normalization accepts the XML. Permissive parsing does not prove correct timing, and stricter rejection does not by itself prove an extractor bug. Preserve that distinction. Any integration remedy must be demonstrated on development data and receive a new configuration identity before evaluation.

4. **Prepare the evaluation run record.** Confirm the frozen scorer/failure fixtures, resumable output identity, logging, disk/resources, and local-first budget. Record processing time for failures. Device-wide WDDM VRAM readings must remain labeled as such; they cannot establish the per-process practical gate. Keep SMB, OLiMPiC, and private diagnostics out of debugging and settings selection.

Once these checks pass for a configuration and the user requests Phase 3, frozen inference may begin for that configuration. Missing readiness for a deferred candidate should not trigger another unbounded correction round.

## What must remain unchanged

- Composition-macro pitch/onset/duration scoring, failure penalties, frozen dataset eligibility, and separate system/page reporting.
- No reference-guided repairs, test-set tuning, or silent conversion-warning suppression. The unresolved ABC round-trip losses remain blockers for claims about faithful ABC conversion, but do not by themselves block non-ABC engines.
- No accuracy ranking from accepted-output counts. Practical eligibility and accuracy are separate; one successful page cannot establish tail latency or memory limits.
- No promotion before verified fine-tuned-HOMR comparison, paired statistics, and the existing replacement gate. A better shipped baseline must not be displaced merely because a fine-tune regresses.

**Next executor task:** prepare the reduced Phase 3 configuration freeze and close the narrow entry checks above. Proceed to frozen evaluation only under an explicit Phase 3 request. There is no justification to restart completed phases or launch another training run.
