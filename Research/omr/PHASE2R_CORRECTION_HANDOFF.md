# Phase 2R bounded correction handoff — 2026-09-25

**Lifecycle update, 2026-10-04:** Completed bounded development correction, 2026-09-25; selective readiness is preserved.
[Plans/status index](../../plans/README.md) identifies the owning historical
plan and its successor. Current research phases belong to [the main plan](../../plans/MAIN_PLAN.md);
dated next-step/stop statements below do not authorize new execution.

> Subsequent [Phase 3 readiness review](PHASE3_READINESS_REVIEW.md): conditional go
> for a reduced roster after configuration entry checks. The Zeus neutral page route
> additionally needs note-bearing join-preservation evidence. No Phase 3 execution
> was started by the review.

## Boundary and decision

This is the development-only correction authorized after the [master review](PHASE2R_MASTER_REVIEW.md). Phase 3 frozen evaluation, fine-tuned checkpoint evaluation, rankings, training, cloud spending, and shipped-engine changes did **not** occur. Frozen manifests and scoring were not edited. All previous Phase 2/2R reports remain intact; new evidence is versioned separately. Accepted output means the adapter produced canonical events, **not** that those events are accurate. No new F1 or candidate ranking is claimed.

The detector-to-crop defect is corrected for both VLM candidates and the two research Zeus page consumers. Rokot's corrected development run still yields no accepted complete page. Audiveris and the neutral Zeus page runner have verified end-to-end development paths. The direct Zeus research-engine path has a separate event-extraction failure. This supports a selective Phase 3 roster decision, not automatic Phase 3 execution.

## Plan-to-evidence check

| Correction task | Validation and outcome |
| --- | --- |
| C1. Correct coordinate contract first | `phase2r_detector.py` saves the exact `predictions.preprocessed` array returned by the same pinned HOMR detector/settings, verifies PNG pixel identity, and records source/detector hashes, dimensions, and coordinate space. `crop_detected_systems` rejects unknown space, hash/dimension mismatch, invalid bounds, and empty detection; it crops the returned image, so both resize and autocrop offsets are implicit without a guessed inverse transform. The detector's five boxes for the representative page match the old detector output numerically. Research-only Zeus runner and direct engine now use the same contract. No shipped Bridge code was changed. |
| C2. Prove before model inference | Regression tests exercise combined autocrop offsets and resizing, box boundaries, source/detector mismatches, and two-staff coverage. Detector-only proof ran before Rokot/Qwen. All five `openscore-6211535-page-1` crops were visually compared with the source: both piano staves and their notes are present across every system. The old first crop used original-image width 2480 and cut the staff; the corrected first crop is 1920×285 in detector space. |
| C3. Progressive Rokot/Qwen validation | One corrected Rokot page was inspected by individual crop, raw ABC, per-system strict conversion, and guarded join before the unchanged-setting 12-control/20-open-first-page rerun. Qwen received one corrected-page check only; its old generated failures are independent. No prompt, precision, or generation-limit change was made. |
| C4. Bounded remaining questions | Audiveris's invalid native export was reproduced and measured; open-reference ABC warning codes were classified without suppression; LEGATO's actual loader graph and default-configuration weight scenario were assessed without downloading weights or proposing cloud spend. Failures now retain total/stage elapsed and available RAM/VRAM samples. |

## Coordinate proof and identities

- Frozen source `data/phase1-development/open/6211535/page-1.png`: **2480×3509**, SHA-256 `b368dd864dc235272728822a578551fbed619cce02265cc52043dea3051c57c8`.
- Detector-returned preprocessed PNG: **1920×2717**, SHA-256 `31bb9cf7a855fe07d56236182b290723d8ceb5660310d1103346dfa708270b57`, coordinate space `homr_predictions_preprocessed`. The detector-only proof, Rokot, Qwen, and corrected Zeus runner produced that same image hash and the same five crop hashes.
- Crop SHA-256, system order: `99567cbd853542d929b41e23803d3932d32d799fca642559474613ca73565ff7`, `a9dc91c21ce2882f354077aa2e334e507e95cf317bb9621b182a6903f6ddb3f3`, `64f453702a720f4740045daca4fb2b60b4c64aea9fa1f1892df228e017c0742a`, `73a3f21806c9ef46fb537a0abb82c159b695738efbff7070d32bff00f524f658`, `aa3d29a8138f1cce2e84adc412979d76ce918c939235fc7f02726d49c7e68a9c`.
- Detector implementation SHA-256 `4ad2a8c2cf88d19db46349fda84c76dc8a60dbad2cac6df9f3405b2ad7b26bc2`; VLM adapter implementation SHA-256 `b4ffcc4f75ba5b0243db3c1314ba421d75e6b69c3c80502ce45e6172626302d5`. Corrected Rokot adapter configuration SHA-256 `61b9370dfa1600068887c63a9e3c72fd4b587d17f59308d4d8c5016f40a12880`; Qwen configuration SHA-256 `93a7470cb86b06ab9f91bfc48661754ebadb3b573653e0c3dc66a042649f02e2`.
- Detector-only image/boxes/crop manifest live in ignored `.runtime/phase2r/correction/openscore-6211535/`. Each VLM page output stores its own detector image and crop manifest. The [corrected page-stage audit](reports/phase2r/corrected-page-diagnostics-v1.json) rechecks source/detector/crop hashes and dimensions for all 20 open pages.

## Corrected development outcomes — counts, not accuracy

| Candidate/configuration | Accepted generated controls | Accepted open first pages | Main observed failure stages |
| --- | ---: | ---: | --- |
| Rokot Q8, corrected page crop, unchanged decoding | 10/12 | 0/20 | Generated: two truncated recognitions. Open: four truncated recognitions, 16 guarded-join failures. |
| Vanilla Qwen parent, one corrected page sanity | Historical 0/12 (unchanged annotated crops) | 0/1 corrected sanity; historical 0/20 used broken crops | First corrected system still lacks an ABC barline; recognition failure. No full corrected Qwen rerun. |
| Audiveris 5.11.0 native page route | Historical 2/12 | Historical 20/20 | Nine generated engine/export failures and one invalid MusicXML export; page route never used the VLM crop path. Single invalid-export control was replayed, not counted as an additional item. |
| Zeus neutral research runner, corrected page crop | Not rerun | 1/1 corrected representative | Segmentation, recognition, conversion, and shared normalization succeeded on this one page. No accuracy claim. |
| Zeus direct research-engine path | Not rerun | 0/1 corrected representative | MusicXML exists, but app-specific canonical event extraction rejects an overfull measure. Shared normalizer accepts the same XML without warnings. |

The [Rokot 32-item aggregate](reports/phase2r/development-trials/rokot-61b9370dfa16-252d8c9a02c2-v1.json) has SHA-256 `dd868b9028a16931ae70c507d4ffb83d87958bf5f8ebe252b3a9b0f6675b3c97`. Its 32 per-item report hashes match. The [strict stage audit](reports/phase2r/corrected-page-diagnostics-v1.json), SHA-256 `a9766bb875d825b08aaeee6445ae4719cdbf25b1c90b0dea678b8f8469a79f75`, found 81 detected systems across 20 pages: 61 have extracted ABC, 34 convert strictly alone, 27 fail strict conversion, and 20 have no ABC after recognition stopped early. Per-system strict warning/error codes include unclosed slurs (9 systems), unmatched ties (10), lyric syllable-count mismatch (9), unmatched slurs (4), unsupported decorations (4), too-few tuplet notes (2), and an unknown token (1); a system may have multiple codes.

On the representative Rokot page, all five images reach recognition; strict croma accepts systems 1, 4, and 5 but rejects systems 2 and 3 for unclosed slurs. The joined ABC fails because voices disagree on ending meter/unit/key state. Two other pages have every system individually strict-convertible, yet the join rejects valid `w:` lyric fields; after ignoring only those fields for diagnosis, their model-produced voice identities also differ across systems. Thus the 0/20 page acceptance rate reflects a mix of recognition, conversion, and join-adapter limitations—not a model-only failure or a clean accuracy estimate. No lyrics, voices, notes, or references were used to repair an output. A further join-policy change would need its own controlled development validation and new identity, not silent inclusion in Phase 3.

All 22 corrected Rokot failed items record total elapsed (12.23–56.90 s) and peak process RAM and sampled VRAM. The corrected Qwen failed sanity records 35.01 s total, 2,439,204,864 B RAM, and 4,996,464,640 B device-wide VRAM. Windows WDDM VRAM fallback is **device-wide**, not per-process usage; it cannot by itself establish the practical VRAM gate.

## Conversion, Audiveris, and LEGATO diagnostics

The strict open-reference ABC audit remains a representation/conversion diagnostic, not candidate scoring. In the previously retained diagnostic run, all 20 open references produced `abc.directive.unsupported` (168 occurrences, chiefly `%%MIDI` metadata); nine items also had `abc.music.unmatched_tie` (45 occurrences), two had `abc.music.unclosed_slur`, and one had `abc.music.unmatched_slur`. Ten warning-tolerant round trips were not exact; the two lowest exact-event F1 values were 0.78669 and 0.90116. Both of those items reported only the unsupported-directive warning, so warning classification alone does not explain their note-event loss. Strict conversion remains the acceptance gate; there was no blanket warning suppression or reference-guided repair.

Audiveris's retained and replayed generated `tie_across_barline` `.mxl` each contain `<divisions>0` while notes have positive `<duration>1`. The shared music21 parser raises `float division by zero` at parse time; this is an invalid Audiveris native export, not an adapter crop error or justification to repair from reference. The new [measured failed replay](reports/phase2r/development-smokes/audiveris-generated-tie_across_barline-935b7fd9e148-06dbf3b4a5ac.json), SHA-256 `858611161e0329add19c3845b3d3293ae704355b3925e4ca67890e4604d2edb9`, records 15.23 s total, 14.10 s engine/conversion, 1.09 s failed normalization, 569,008,128 B peak process RAM, and no available VRAM sample. Earlier Audiveris reports are unchanged.

The pinned LEGATO loader constructs its dedicated decoder from `guangyangmusic/legato` then calls `MllamaVisionModel.from_pretrained` for the external encoder; it does **not** load the complete 11B language model for inference. Upstream inference moves the combined model to CUDA before its optional FP16 cast. The dedicated checkpoint file is 429,478,304 B. A meta-device count using the installed Transformers *default* Mllama vision config gives 836,288,019 parameters (1.56 GiB FP16 or 3.12 GiB FP32 vision weights alone). This is not the exact pinned encoder configuration or observed peak; decoder, activations, KV cache, framework overhead, and load/cast transients remain. Neither 6 GB compatibility nor impossibility was demonstrated. Recognition weights were not downloaded; no cloud cost was incurred. [LEGATO readiness](LEGATO_READINESS.md) now corrects the old full-repository-size inference.

## Zeus page-path distinction

Both research Zeus page consumers had applied HOMR detector-space boxes to original pages. `phase2_zeus_runner.py` and `zeus_engine.py` now crop the saved detector-returned image through the same checked helper. The corrected neutral-runner [page smoke](reports/phase2r/development-smokes/zeus_app-openscore-6211535-page-1-2945b681ae6b-no-runtime.json), SHA-256 `42aa111794baf314d4ab5a091caf54c004576733d6cfe8ed9494ba469cc076e1`, accepted one representative page under configuration SHA-256 `2945b681ae6b8143d37b6e5b95f14e30ffc0aefa5a8d1e424b1f8ac74493dbc5`. It took 65.19 s recognition/conversion/joining plus 0.64 s shared normalization, with 1,060,704,256 B peak process RAM and 1,179,648,000 B device-wide WDDM VRAM. Its detector image and all five crop hashes match the VLM proof. The filename's `no-runtime` suffix is a legacy smoke-runner naming limitation; the full configuration/source hash and runtime path are in the report.

The direct `zeus_engine.py` path reached five per-system MusicXML files and a combined XML but failed in `extract_canonical_events`: `Measure 0 on staff 0 exceeds its time signature`. The shared normalizer accepted the same combined XML without warnings, so this is a distinct app-specific extraction/timing-validation failure. The [measured failed attempt](reports/phase2r/zeus-engine-page-measured-v2.json), SHA-256 `e5d1a35614fe282a94c46099f1bda3d3d166ed986d23a4680f19b65bd34621a0`, records 20.00 s, 1,201,963,008 B peak process RAM, and 1,179,648,000 B device-wide WDDM VRAM with partial XML/log hashes. An earlier diagnostic-wrapper packaging attempt failed after model inference because it relativized a relative path against an absolute workspace; that partial output was preserved, the wrapper path handling was fixed, and the one measured v2 attempt completed. No model-setting change or reference-based timing repair occurred.

## Candidate readiness for a separately authorized Phase 3

| Configuration | Segmentation / recognition / conversion / joining distinction | Readiness decision |
| --- | --- | --- |
| Shipped HOMR | Mandatory historical control; this correction did not rerun its existing runtime. | Carry forward subject to ordinary Phase 3 identity/input freeze; no new accuracy claim. |
| Zeus upstream annotated-system path | Does not use page segmentation; historical Phase-2 development smoke succeeded. | Carry forward as system-level configuration, not complete-page replacement evidence. |
| Zeus neutral corrected page runner | All four stages passed on one corrected open development page. | Ready for complete-page configuration freeze, with one-page coverage limitation disclosed. |
| Zeus direct research-engine/app path | Corrected segmentation and XML generation; app event extraction fails on timing validation. | **Not ready** as direct app path; do not substitute neutral-runner success for it. |
| Audiveris native page path | Own page detection and conversion; 20/20 open first pages accepted, but generated failures and invalid export persist. | Ready as failure-penalized complete-page baseline; accuracy unmeasured here. |
| Rokot Q8 corrected page path | Segmentation fixed and all 20 pages detected; recognition truncation, strict ABC conversion failures, lyric/voice/state join limitations remain. | **Exclude this configuration from complete-page Phase 3** until a separately validated end-to-end remedy exists. Do not infer intrinsic model accuracy from 0 accepted pages. |
| Qwen parent corrected page path | Same verified crop; first system still emits invalid ABC. Historical 0/12 generated controls independently failed. | **Exclude current configuration**; bounded sanity exhausted, no prompt search authorized. |
| LEGATO | Vision-encoder-plus-decoder load graph assessed, but recognition weights/runtime unprovisioned; basic converter fixture only. | **Unavailable, not scored**. No 6 GB impossibility claim. |
| Fine-tuned HOMR, PR #156, MuSViT | Fine-tuned checkpoint selection belongs to Phase 4; PR #156 needs compatible verified weights; MuSViT needs a usable decoder or separate training proposal. | Do not invent Phase 3 pretrained results for unavailable/conditional entries. |

## Integrity, tests, and stop state

- New development reports: 32 corrected Rokot, one corrected Qwen, one Audiveris replay, and one corrected Zeus neutral-runner page. All 35 per-item declared artifact sets plus the measured direct-Zeus report were checked: **36 reports, 278 declared artifacts, zero missing/hash mismatches**. The Rokot aggregate's 32 report hashes match; the corrected stage audit verified all 81 page crop hashes/dimensions and detector-source identities.
- Research suite: **101 passed**. Selected bridge detector/normalizer suite: **22 passed, 6 subtests passed**, one expected `music21` warning. Python compilation checks passed. Phase-1 report and its 15 artifact hashes remain valid; all four historical Phase-2 artifact hashes match. `git diff --check` passed apart from existing Windows line-ending notices.
- No Phase 3 evaluation process was started. No SMB, OLiMPiC, or private diagnostic candidate inference, new training, cloud rental, fine-tune alteration, or shipped app publish occurred. The old Rokot/Qwen page reports remain records of the broken input path, not eligible evidence for model-only exclusion. See the [job record](reports/phase2r/job-record.md) for commands, logs, failed-attempt history, and resume details.

**Next action for the master-plan agent:** review the selective roster and the two unresolved adapter-specific joining/extraction issues. If a different Rokot join policy or direct Zeus app-path repair is desired, authorize a separately bounded development change with a new configuration identity and fresh validation. Otherwise a later explicit Phase 3 request may freeze only ready configurations. Do not advance automatically from this handoff.
