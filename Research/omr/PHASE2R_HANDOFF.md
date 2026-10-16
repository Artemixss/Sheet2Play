# Expanded OMR comparison — Phase 2R handoff

**Lifecycle update, 2026-10-04:** Completed historical Phase 2R with selective candidate readiness; the bounded correction followed.
[Plans/status index](../../plans/README.md) identifies the owning historical
plan and its successor. Current research phases belong to [the main plan](../../plans/MAIN_PLAN.md);
dated next-step/stop statements below do not authorize new execution.

> **Subsequent bounded correction, 2026-09-25:** see the active
> [Phase 2R correction handoff](PHASE2R_CORRECTION_HANDOFF.md). It fixes the crop
> coordinate contract, reruns development evidence, and supersedes this document's
> candidate-readiness conclusions. Original reports and observations below remain
> historical, not overwritten. Phase 3 has not started.

> **Subsequent master review, 2026-09-24:** the [master review](PHASE2R_MASTER_REVIEW.md)
> found a confirmed detector-to-crop coordinate mismatch in the VLM page adapter.
> Preserve the execution results below, but do not interpret their page failures as
> model-only evidence or exclude Rokot before correcting and validating that path.
> The review also qualifies the untested LEGATO hardware conclusion. Phase 3 remains blocked.

## Boundary and reconciliation

Phase 2R is the expanded plan's development-only readiness step. The original Phase 2
contract/report remains historical evidence, not an eligible ranking. Phase 3 frozen
evaluation, later fine-tuned evaluation, rankings, training, and production promotion have
not started. No SMB, OLiMPiC, or private diagnostic inference was run for this step.
No cloud compute was rented and no private library file was transferred.

The [canonical plan](../../plans/archive/2026-09-26-omr-screening-comparison.superseded.md) and [versioned candidate configuration](comparison-config-v2.json)
govern the expanded roster and later fine-tuned-HOMR approval baseline. The
[readiness review](PHASE2_READINESS_REVIEW.md) recorded four gaps; the old
[Phase 2 handoff](PHASE2_HANDOFF.md) and its reports were not overwritten. The
[interruption handoff](PHASE2R_INTERRUPTION_HANDOFF.md) records the earlier stop and
download-resume state. The [job record](reports/phase2r/job-record.md) gives executable
commands, input identity, logs, and resume rules.

## Phase 2R task breakdown and evidence

| Task | Outcome and evidence |
| --- | --- |
| Reconcile and protect the freeze | The Phase-1 freeze and four historical Phase-2 report hashes are checked before every development smoke. Separate Phase 2R reports live under `reports/phase2r/`; no historical report or frozen manifest was changed. |
| Execute failure contracts | Empty canonical output and missing-middle-system paths now execute detection/adapter failure and zero-F1 aggregation checks instead of relying on literal-success fixtures. `test_phase2r.py` also rejects scoring an unavailable candidate as zero. |
| Verify real runtimes | [runtime-identity-v1.json](reports/phase2r/runtime-identity-v1.json) records actual installed source/patch, weight, tokenizer, converter, executable, model, projector, and CUDA-library hashes/versions. Official llama.cpp b11124 CUDA 12.4 runs on the local RTX 4050. |
| Implement expanded adapters | Rokot Q8 and vanilla parent Qwen Q8 use the same deterministic ABC adapter, annotated-crop and frozen-detector complete-page paths, strict croma 1.2.1 conversion, typed failures, raw output, and guarded voice/state merge. Audiveris 5.11.0 runs unattended on native development pages, with documented small-image scaling. |
| Exercise development inputs | The frozen 12 generated controls and 20 open compositions were hash-audited. Candidate trials use every generated control and the first page of every open composition, not all 122 open pages and not a whole-composition accuracy claim. |
| Conditional candidates | LEGATO's native conversion path passed, but full recognition is locally unavailable under the pinned 11B-vision dependency; [LEGATO_READINESS.md](LEGATO_READINESS.md). MuSViT has no verified recognition decoder checkpoint and remains “requires training—not evaluated”; [MUSVIT_FEASIBILITY.md](MUSVIT_FEASIBILITY.md). |

The runtime-identity report's SHA-256 is
`5704beae46871747edc5ab1def0ef4bd435949b5f13fbc72fc42a28f3ebde6a8`.

The frozen development-reference [audit v1](reports/phase2r/development-audit-v1.json)
and [diagnostic audit v2](reports/phase2r/development-audit-v2.json) cover all 32 records,
including ties, tuplets, independent voices, meter changes, and multi-page works. All
12 generated references passed strict croma round-trip. All 20 open reference
projections raised strict warnings; a separately labeled, non-scoring diagnostic
round-trip had mean exact-note F1 0.97847 and minimum 0.78669. This is reference
projection loss, not an excuse to waive strict candidate conversion or a candidate
accuracy score. Full reference-projection coverage and candidate first-page inference
are separate evidence tracks.

## Runtime and conversion facts

The official llama.cpp b11124 CLI and CUDA 12.4 companion ZIP match pinned release
hashes; `--list-devices` detects the RTX 4050 (6140 MiB). Rokot and Qwen Q8 text
weights and matching vision projectors match pinned file hashes. croma 1.2.1 is pinned
by hash. The installed HOMR source commit is verified and its five ONNX weights/four
tokenizers were hashed. LEGATO source is clean at
`179c228d3d5f67113cf739b44891b3abe046f1dc`, and the genuine upstream
ABC-to-MusicXML path produced four normalized notes without warning on a small native
fixture. Its 11B vision dependency is not locally runnable on 6 GB VRAM/15.2 GB RAM;
no recognition result or zero score is assigned. Audiveris's extracted 5.11.0
executable and installer match pinned hashes, and `-version` reports the expected
commit. Files without an independently published expected digest are labeled
`hashed`, not falsely `verified`, in the identity report.

The Rokot/Qwen page adapter rejects missing/empty declared voices instead of silently
filling them from a reference. The structured ABC merge preserves voice order, meter/key
state, and cross-system ties; executed tests cover two-system ties, tuplets, independent
voices, meter changes, mismatched voice identity, and missing systems. Model-generated
invalid/truncated notation remains a typed failure with raw output retained.

## Completed Audiveris development evidence

The final captured-artifact [Audiveris trial report](reports/phase2r/development-trials/audiveris-65cbbc866b8d-06dbf3b4a5ac-v1.json)
(SHA-256 `c8ad7a8bed2266045a12cf00714b4e9ad037a4d8c7c8bae7f7acd1251e38e7a7`)
has 22 successes and 10 failures across 32 development inputs: both successful
generated controls and all 20 first pages of open compositions passed. Nine other
generated controls failed Audiveris transcription/export; one emitted MusicXML that
the shared normalizer could not parse (`float division by zero`). The generated images
were too small for unattended Audiveris at their original ~9-pixel staff interline,
so the research adapter scales inputs under 2000 pixels wide with Lanczos 2–4x and
300 DPI metadata. It does not change the frozen source image. Scale, prepared-image
hash, preprocessing time, and artifact are recorded on success; engine-level failures
record full console log and nonempty partial files as hashed artifacts. All ten final
failed results have at least two declared artifacts. The normalization-failure result
records the partial native `.omr` and `.mxl`; its engine-owned log remains under the
ignored per-item runtime directory. The earlier pre-fix failed and 22/10 reports were
preserved rather than overwritten. None of these development outcomes is a frozen
evaluation ranking.

## Rokot Q8 development evidence

The [verified 32-item Rokot aggregate](reports/phase2r/development-trials/rokot-fb28064ca084-252d8c9a02c2-v1.json)
(SHA-256 `2a57b238f6a719dc51e99c78f20d2bf6f128ce235af3d29ac481d733401e28af`)
references hash-checked immutable per-item reports. Ten of 12 generated annotated
controls succeeded. Two controls failed `TRUNCATED_GENERATION` after repetitive ABC.
All 20 first-page open-composition trials failed: three `INVALID_NOTATION`, eight
`STITCH_INVALID`, and nine `TRUNCATED_GENERATION`. The first representative page's
five detected systems reached the join, where a declared second voice had no music;
the adapter refused to silently fill it. Other raw outputs show repeated tuplet
syntax or bar patterns until truncation. These are observed model-output failures,
not missing CUDA or a parser-only failure. No complete-page development success is
claimed, and Rokot is not ready for a complete-page frozen comparison without a
new development-only remedy and validation.

The first generated Rokot crop succeeded on the pinned GPU runtime with 8.84 seconds
recognition and 2.50 GB peak process RAM. Its sampled 5.48 GB VRAM reading is a
**device-wide Windows WDDM fallback**, not per-process usage; successful controls
peaked as high as 5.98 GB device-wide. The earlier CPU crop and page smokes remain
separate historical functional evidence and are not used for local-GPU claims.
Failure results retain the raw ABC/text available at the point of failure but do not
all have usable memory/timing fields; they must not be treated as successful runs in
latency summaries.

## Vanilla Qwen3-VL-2B-Instruct parent control

The [32-item Qwen aggregate](reports/phase2r/development-trials/qwen-eb8b6de1075a-252d8c9a02c2-v1.json)
(SHA-256 `78b0679bdd235c9924916996893bb45bab68dd237f7f0636f87830183597abf5`)
records **32 `INVALID_NOTATION` failures**: all 12 generated controls and the first
page of each of 20 open compositions. Each result retains at least one raw-output
artifact. The initial CPU prompt emitted repeated non-ABC staff metadata; a revised
development-only ABC prompt plus deterministic seed/temperature and 1024 image tokens
produced repeated rests or other notation without a barline on the verified local
GPU. Crop and complete-page paths were both exercised, with no accepted output.
This is a parent-model control failure under the tested settings, not proof of a
missing model/runtime and not an accuracy score. Qwen is not ready for Phase 3
frozen comparison under this configuration.

## Scope limits that must survive handoff

- A first page per open composition is development *coverage*, not complete-composition
  accuracy. The other 102 open pages were not inferred by each candidate in this step.
- The strict croma warning result for open **references** is not interchangeable with
  direct candidate ABC conversion failure. Diagnostic, warning-tolerant reference
  round-trips are not scoring inputs and must not silently relax the frozen protocol.
- Failed VLM trials retain raw text and typed failure but their generic failure
  wrapper does not recover full per-system RAM/VRAM/timing measurements. Success
  measurements are development-only and WDDM VRAM fallback is device-wide.
- A local LEGATO recognition result is still absent. The dedicated checkpoint and
  external vision weights were not downloaded or hashed locally, and the converter
  fixture is not a substitute for model inference. MuSViT is not a runnable candidate.
- No current Phase 2R development result authorizes engine replacement, a ranking,
  frozen evaluation, cloud spending, or training. The master-plan owner must decide
  candidate exclusions and whether any further readiness remedy is worth pursuing
  before a separately requested Phase 3.

## Validation against the Phase 2R plan

| Readiness requirement | Result |
| --- | --- |
| Executed empty-output, missing-system, typed-failure, and zero-F1 checks | Passed in the research test suite; unavailable candidates are rejected as scores. |
| Real file/runtime identity | Passed for installed HOMR, Zeus, croma, Audiveris, Rokot/Qwen weights/projectors, llama CLI, and CUDA DLLs. LEGATO source/converter were verified, but its recognition weights were deliberately not downloaded and cannot be marked ready. |
| Genuine development inference and conversion | Audiveris: 22/32 success, with nine engine failures and one invalid XML normalization. Rokot: 10/32 success, **0/20 first pages**. Qwen: **0/32**. LEGATO recognition remains unavailable; its real converter path passed a basic native fixture. |
| Ties, tuplets, voices, meter changes, and joins | The frozen 32-input audit inventories these traits; strict executed conversion/merge fixtures pass. Real Rokot page joins fail on missing/empty model-produced voice content; no reference-guided repair was applied. |
| MuSViT decoder/checkpoint feasibility | Requires training—not evaluated. No decoder checkpoint or faithful converter was verified. |
| Preserve frozen evidence and stop before Phase 3 | Passed: Phase-1 report SHA-256 remains `96266247b0ed475f7a9dfec8248d813cb867ba7a16c6f56e00c321b3de93b211`; all 15 Phase-1 artifact hashes and four historical Phase-2 artifact hashes match. New reports are separate; no frozen evaluation inference ran. |

All 96 final per-item development results (32 each for Audiveris, Rokot, and Qwen)
were re-read with input/configuration identity checks, and every declared artifact
matched its recorded SHA-256. Research tests: **97 passed, 3 subtests passed**.
Bridge tests: **26 passed, 6 subtests passed**, with one expected `music21` warning
in the unreadable-clef test. `git diff --check` passed (Git emitted only the existing
Windows line-ending notices). These are research-only changes, so the shipped app was
not rebuilt or republished. The Phase-1 and historical Phase-2 reports remain frozen.

## Master-plan handoff decision

Phase 2R execution is complete **with unresolved candidate readiness**, not a blanket
go-ahead for Phase 3. Audiveris is runnable but must carry its development failures
and invalid-export case into any failure-penalized later comparison. Rokot and vanilla
Qwen lack a successful complete-page development path under the pinned configurations;
do not freeze them for complete-page evaluation or claim practical suitability on the
crop successes. LEGATO recognition remains unavailable on this local hardware, and
MuSViT requires a separate training authorization. HOMR PR #156 still lacks verified
compatible weights, and the fine-tuned HOMR checkpoint belongs to later Phase 4
verification/selection.

The master-plan owner should decide whether to approve another bounded development-only
remedy for Rokot/Qwen or explicitly exclude their current configurations, and whether
to arrange a separately costed LEGATO runtime. Recheck the open-reference conversion
warning ledger before using an ABC candidate. Any Phase 3 evaluation still requires a
new explicit request, ready frozen configurations, and the original Phase-1 scoring
rules. Do not infer promotion, training, or a ranking from this handoff.
