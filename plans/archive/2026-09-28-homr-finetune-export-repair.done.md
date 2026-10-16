# Verify and admit the existing HOMR fine-tune

**Plan ID:** `2026-09-28-homr-finetune-export-repair`.
**Lifecycle:** Completed Phases 1–4 on 2026-09-28; archived on 2026-10-04.
[Completion/job record](../../Research/omr/reports/screening/finetune-export/job-record.md)
and [authorized Phase 4 closeout](../../Research/omr/reports/screening/v1/stage4-homr/job-record.md)
record the completion evidence. Earlier stop statements are dated request
boundaries; they do not reopen this completed plan.

**Status: completed (Phases 1-4, 2026-09-28); historical reference.** Current execution
phases belong to [MAIN_PLAN.md](../MAIN_PLAN.md). The instructions below record the original
scope and subsequent authorizations; they are not a queue to rerun completed work.

Approved scope: evidence-led fixes, no retraining, and a hard stop when required artifacts or information are unavailable. On 2026-09-28 the user requested Phases 1, 2, and 3 only; stop before Phase 4.

**Subsequent authorization, 2026-09-28:** The user requested the HOMR-only canonical
Stage 4, including repaired fine-tune and corrected 455 screening prerequisites.
The [completed job record](../../Research/omr/reports/screening/v1/stage4-homr/job-record.md) preserves the
combined manifest, fresh admissions and execution evidence. Fine-tune screening and
all 59 scores, corrected 455 and the [HOMR-only Stage 4 analysis](../../Research/omr/reports/screening/v1/2c98d5638c36/reports/homr-only-stage4-e35f73ca9f75/REPORT.md)
are complete. The earlier Phase 4 stop is
historical; confirmation, training and promotion remain outside this request.

## Findings

The confirmed intake blocker was inconsistent export provenance. Remote, GitHub, and local decoder bytes match `54c4940a2c8f8ca2c340744f29ea6a90a1645973ee7195d127d1b2c776609fce`, while the historical manifest declares `daee4ce3029e53af46bd3f3ea08528ed2af3e5770cb3e75f4fc67926bdd5c685`. The old hash remains preserved as stale evidence; the verified final binaries have a new provenance manifest.

The remote epoch-14 checkpoint exists and matches its recorded hash. Final decoder fusion rewrites the ONNX file and could explain an early hash, but that explanation is unproven.

The approved source/config/tokenizer/verification bundle arrived through private `Artemixss/report` commit `9bf0d477aa75e8c4a7b48ad6b9fdae2d24c1fab7`. Strict checkpoint and wrapper loads passed. CPU parity passed at atol=0.02/rtol=0.02 on two encoder inputs and three decoder calls, including cache-bearing calls; repeated greedy generation matched exactly and reached EOS after 63 tokens. The remote CUDA provider failed at the first fused decoder cache step (CUDA error 9). Local complete-page runs execute the same verified models successfully on CUDA; the remote provider failure is retained separately.

The first local page attempt failed because the new model-identity guard rejected required RapidOCR models during conversion. The focused repair pins and permits those three auxiliary models while requiring CUDA for HOMR encoder, decoder and segmentation. No retraining, re-export, binary transfer, or shipped runtime change was needed. [The execution record](../../Research/omr/reports/screening/finetune-export/job-record.md) preserves the failed attempt, corrections, commands and evidence.

## Phase 1 — authoritative artifact bundle

**Completed, 2026-09-28.** The approved bundle is preserved at
[remote-9bf0d47](../../Research/omr/reports/screening/v1/finetune-export/remote-9bf0d47/ARTIFACTS.md).
All 29 transferred Git blobs and 28 SHA-256 inventory entries verified. Existing
local ONNX bytes match the new provenance; no new binary transfer occurred.

- Continue through the existing remote chat, `I'm fine-tuning an OMR model (homr) on this PC to fix rhyth…`, thread `01a0a9eb-4674-7342-aecd-0c437ad6704a`, host `remote-control:env_e_6aaa7759fbb4832ab2323945df4f2a2c`. Recheck processes before execution.
- Use `/root/Sheet2Play/Research/omr/vendor/homr/current_training/checkpoint-135674/model.safetensors`, SHA-256 `bb077e964069145996376c209a035a473986c255143e73e8777bfbbf908a6de0`. Preserve recorded epoch-14 validation selection and record the final checkpoint separately.
- Capture training commit `457e7c6518a10ba755db2e60883419e56c4d7369`, relevant uncommitted patches, configuration/preprocessing, exporter script/logs, dependency versions, all four tokenizer files, and source-generated vocabulary ordering.
- Transfer small provenance files through private `Artemixss/report` and binaries through private release assets. Hash after transfer, preserve originals, and keep private music local.

## Phase 2 — export verification and evidence-led repair

**Completed, 2026-09-28.** [Verification evidence](../../Research/omr/reports/screening/v1/finetune-export/remote-9bf0d47/verification.json)
and [provenance v2](../../Research/omr/reports/screening/v1/finetune-export/remote-9bf0d47/provenance-manifest-v2.json)
bind the unchanged checkpoint/export pair. CPU parity passed; the remote CUDA provider
limitation remains recorded and local CUDA page execution passed in Phase 3.

- Strictly load the checkpoint in its matching source/runtime; reject missing or unexpected learned parameters.
- Check model pairing, ordered vocabulary semantics, special tokens, head dimensions, precision, preprocessing, and decoder cache/state interfaces. Do not substitute the HOMR 455 contract.
- Compare checkpoint execution with the existing ONNX pair on fixed development inputs: encoder, initial decoder step, cache-bearing steps, and deterministic complete generation. Declare tolerances before comparison and retain numerical/token evidence.
- If equivalence passes, create a new provenance manifest binding the existing binaries to checkpoint and verification evidence. Preserve the old manifest; do not assert the fusion hypothesis as fact.
- For a demonstrated defect, repair its boundary and export into a fresh directory. Hash after all fusion writes finish and repeat verification. Do not retrain, search checkpoints, or optimize inference settings.

## Phase 3 — actual comparison-path integration and development admission

**Completed, 2026-09-28.** [Final manifest](../../Research/omr/reports/screening/v1/manifest-v4-502777eed80a.json),
[admission](../../Research/omr/reports/screening/v1/2c98d5638c36/admissions/fine_tuned_homr/9fa13d27f0b7/admission-23d1108e5364.json)
and [local verification](../../Research/omr/reports/screening/finetune-export/local-entry-verification.json)
record three successful complete development pages. Full regression: 213 passed,
2 skipped, 9 subtests passed. **Historical Phase 3 stop:** Phase 4 had not started at the end of the original
repair-only request; its later authorization and completion are recorded below.

- Register `fine_tuned_homr` in research preparation, development, admission, inference, and scoring commands with an isolated source/runtime and explicit verified model paths.
- Pin checkpoint, weights, source patches, vocabularies, preprocessing, runtime/provider, launcher, normalizer, and verification evidence in candidate identity.
- Derive a new content-addressed manifest from v4, preserving 59 pages, 18 composition groups, frozen scoring, and the 90% RAM policy. Preserve historical manifests.
- Run representation/conversion fixtures, the representative complete development page, then the existing three-page development set through detection, recognition, MusicXML, and shared normalization. Keep native output, canonical events, logs, resource samples, and loaded-file identities.
- Require successful complete-page output and fresh admission for the exact candidate configuration. Run focused tests followed by the complete research/bridge regression suite. Update handoffs and startup links.
- Stop here: no screening-page inference or scoring is authorized by the current request.

## Phase 4 — screening and report (completed under the subsequent Stage 4 request)

**Completed, 2026-09-28.** Fresh combined-manifest admission and all 59 fine-tune
inference outcomes/scores verified; zero failed pages, primary F1 0.3844, total session
61.7 minutes. The final HOMR-only report above includes shipped and corrected 455
comparisons, uncertainty, duration diagnostics, resources and the stopping decision.
The original repair-only request stopped after Phase 3; execution followed the user's
later explicit authorization. No confirmation or promotion followed.

- Screen all 59 frozen pages with one worker, five-page chunks, half-CPU thread limits, below-normal priority, and no concurrent scoring. This requirement is fulfilled; do not repeat the completed screen.
- Use five-second monitoring, 90% RAM/device-wide VRAM thresholds, 30-second pressure window, and four-hour sessions. Resource interruptions stay pending; completed model failures retain frozen scoring treatment.
- Report against hash-verified shipped-HOMR results under their original manifests. Keep timing/resource policies visible; reject invalid historical HOMR 455 results.
- Report frozen transcription metrics, paired composition statistics, duration diagnostics, failures, OMR-NED, resources, latency, and training overlap. Stop before confirmation or promotion.

## Validation and stopping conditions

- Reject corrupted weights, mismatched pairs, reordered vocabularies, wrong source imports, missing provenance, stale admissions, and silent fallback to shipped weights.
- Test sample/manifest immutability and interrupted/resumed work without changing failure semantics.
- Stop when a required artifact or information is unavailable. Report its exact path/revision, expected identity when known, required contents, owning machine, transfer route, and next verification command. Do not repeat unchanged failures or guess configuration.
- Continue fixes only for demonstrated defects with a testable remedy. Stop when the next step requires training, speculative settings search, or unrelated pipeline work.
- Phase 3 completion means verified provenance and successful complete-page development admission. It does not mean the 59-page screen or production promotion occurred.
