# Proposed bounded HOMR 465 trial and adoption path

2026-10-08. Proposal from the completed
[HOMR timing/465 plan](../../../../../plans/archive/2026-10-06-homr-timing-465.done.md).
**This is a reviewable follow-up proposal, not a selected execution plan.**
Phase 4 did not authorize implementation, inference, trial publication or adoption.
[Recommendation](REPORT.md), [acceptance ledger](acceptance-ledger.md).

## Proposed decision

Select a new bounded plan for a **visible, opt-in no-title 465 app trial**, starting
with isolated qualification in the intended app Python environment. Retain shipped
HOMR 426 as the default and keep its source, weights, caches and user library.
Do not swap 465 weights into installed `site-packages/homr`. The measured candidate
is a distinct source/model/pipeline bundle, including native multi-voice handling
and #171/#178.

## Fixed starting identity

| Component | Proposed starting value |
| --- | --- |
| Candidate | `homr-465-upstream`; configuration SHA-256 `9e619e47fd0317b6a7d1da5207985e1120acefc499a111649c5b7cdb1e339122` |
| Source | `Research/omr/.runtime/homr-465-upstream/source`, revision `33baa326900faa12702df8c4bdcbea034a3d6a34` |
| FP16 encoder | `Research/omr/.runtime/homr-465-upstream/encoder/encoder_pytorch_model_465-597144cab54c8f6d0f6c9619df5c5312694eadd6_fp16.onnx`; SHA-256 `50823c061533328f5e64df016d3ed16eb9071a9f5c5ee8621646cf9ac9c8a992` |
| FP16 decoder | `Research/omr/.runtime/homr-465-upstream/decoder/decoder_pytorch_model_465-597144cab54c8f6d0f6c9619df5c5312694eadd6_fp16.onnx`; SHA-256 `aaac38c4f4be13ec587325486f29a60a919924f0eb82d35b52d4a2e7126dfbe0` |
| Segmentation model | Existing pinned segnet 308 FP16; SHA-256 `60f495496cb41473c0521d0811d8f44b9d5cff892d287974a8aebb3eaee2fa83`; exact path in frozen configuration |
| Python | Existing `Bridge/.venv-homr-gpu/Scripts/python.exe`, currently 3.11.9; per-process imports of isolated source, with installed package files preserved |
| Native inference | `CUDAExecutionProvider`, eight intra-op / one inter-op thread, native page detection/crops/decoding/export; 300-DPI inputs |
| Title/settings | `title_detection=false`, no selected-staff restriction, no source/weight edits, unchanged production normalizer and retained native XML arguments |
| Contract | Separate [465 contract](../../../homr_465_contract.json), all six heads and five ordered positions; preserve 455 contract |
| App prototype | [Phase 3 isolated revision branch](../phase3/runtime-repair.json); it is insufficient to wire candidate inference/cache selection |

The [frozen configuration](../phase2/candidate-configuration.json) is the detailed
authority. Using another interpreter already changes runtime identity; freeze a
new trial identity after admission without overwriting Phase 2's configuration.
Keep the installed music21 10.5.0 versus research 9.9.1 distinction visible.
No new packages, model downloads or cloud jobs are planned. Report any newly
demonstrated dependency need before acquisition or dependent execution.

## Proposed bounded sequence and acceptance

| Step | Work and bound | Acceptance / stop |
| --- | --- | --- |
| 1. Intended-runtime qualification | Verify interpreter, module origins, segmentation/encoder/decoder digests, ONNX interfaces/providers and settings. Fresh CPU/GPU admission. Candidate probes: generated baseline and OpenScore 6211535 page 1, followed by the existing 32 development inputs for candidate and fresh shipped-source control; at most 64 full captures, including probes | Every input has a complete receipt or explicit model failure. Settings/source/model paths are reproducible; no unreviewed resource interruption or new runtime incompatibility. Compare authoritative generated controls; OpenScore stays diagnostic-only |
| 2. Isolated app integration | Build one research app profile in a separate trial directory, with a visible engine selector and scratch library/cache. Wire native candidate image/PDF recognition through Bridge/normalization/MIDI/controller. Reuse 12 controls and representative voice/tie/tuplet/pickup/tempo fixtures | Actual selected source/model/provider and returned engine/model/settings identities agree. All persisted cache contracts and reopen behavior pass; shipped engine and existing caches are untouched |
| 3. Controlled GUI/audio trial | Launch the separate trial EXE against that scratch library. Import/preview generated controls, inspect the two corrected and two regressed measures, held notes/overlap/tempo, then replay a bounded existing diagnostic score | Report actual launch/import/reopen identity, correct dispatch/cache behavior and observed physical sound. Preserve known recognition harms and tie limitation. Record any new harm and user correction effort if measured; perfect recognition is not a trial-closure requirement |
| 4. Trial closeout decision | One report/ledger with receipts, identity, before/after development behavior, resource/runtime checks, remaining musical errors and rollback status | Decide whether an eligible confirmation/adoption review is justified; stop before that evaluation or production publication |

For new trial code, run the affected contract/behavior fixtures first, then one
representative development item, the complete relevant Research/Bridge regression
and fresh frontend/playback tests. Repeat the 32-input downstream manifest where
its input and code identities remain appropriate, adding integration/cache/reopen
coverage for the new selector and launcher. Test wrong revisions, missing assets
and unavailable providers as explicit failures. A research build/test pass alone
does not establish that the user's installed executable received any change.

Candidate and control in step 1 share the intended runtime and page/scoring rules;
the historical Phase 2 screen stays frozen. Runtime identities must match before
reusing cached outputs. Do not choose changes from screen losses, silently rerun
the 59-page comparison or call the development trial untouched confirmation.
If any new change alters musical outputs, select it on development only, freeze
a separate profile and obtain a new decision for its required comparison. A shared
normalizer change would require symmetric evaluation and is outside this proposal.

The 64-capture ceiling bounds qualification; it does not authorize repeated attempts
until success. Report missing/invalid/timeout outputs under frozen failure rules,
and retain pending resource interruptions separately. Existing research means
of approximately 15–16 seconds per page are descriptive; estimate installed-runtime
time from the admitted probes before scheduling the remaining chunk.

## Runtime, cache and library contracts

- Use an isolated launcher with explicit pinned source and model locations for
  each process. Verify imported modules and all three active ONNX paths/providers;
  fail visibly on an identity mismatch or unavailable CUDA provider. Do not fall
  back silently to a different checkpoint or update a moving upstream branch.
- Assign a distinct candidate engine revision, exact model-pair identity and
  settings fingerprint incorporating title policy, segmentation identity,
  normalizer identity/version and decoder settings. Persist and validate them
  in both Bridge JSON and app cache manifests. A changed identity creates a new
  cache entry; it must not reinterpret or delete the shipped 426 caches.
- Stage the research EXE, logs and a scratch library under a separately identified
  `Research/omr/.runtime/homr-465-app-trial` directory. Verify actual library/settings
  resolution before launch; do not write the user's `%LOCALAPPDATA%/Sheet2Play`
  library. Provide a visible opt-in selector and a direct return to shipped HOMR.
- The Phase 3 probe used explicitly selected direct-XML ingestion. The default
  MusicXml runtime resolver, model revision and `SongCache.GetOmrSettings` branches
  remain incomplete. If the proposed app path uses that route, complete those
  demonstrated contracts in the isolated profile and test persistent import.
  A candidate image/PDF engine may normalize its native XML internally; its
  qualification does not require an unrelated production MusicXml repair.
- Keep title OCR disabled and label the trial accordingly. Enabling title OCR
  requires a separately versioned development equivalence/resource check; prior
  title allocation failures remain unresolved. Preserve the 0.055-second audio
  offset and test physical output without guessing a replacement value.

## Safeguards and stop conditions

Use the unchanged guarded Windows supervisor for substantive jobs, with one heavy
worker, 85% physical-RAM/system-commit stops, 4 GiB reserve and aggregate worker
cap, 16-process containment, bounded per-capture deadlines and the four-hour
unattended-session boundary. Inspect live jobs/locks and permissions before launch.
Local 6 GB GPU admission is separate, with the retained 90% device-VRAM limit and
no competition with the existing fine-tune. Keep the 5% five-hour allowance stop.
Record command/cwd/identities/logs before each long job. Do not invoke Git during
recovery or automatically retry a pressure failure; preserve receipts and partials.

Stop dependent work on incompatible interfaces/imports, unexpected source/model
selection, unresolved resource interruption, new unexplained musical conversion
harm, cross-profile cache reuse or a write to the user's production library.
Report the exact first failing stage and missing evidence. A practical blocker
would return the decision to retaining shipped HOMR; a shipped-exporter fallback
still requires separate selection and authorization. Do not hard-code reference
notes/durations or train to remove the known recognition errors.

## Later confirmation and production adoption

A successful bounded trial is operational evidence. A later accuracy-led adoption
decision must retain the [frozen protocol](../../phase1/scoring-protocol.json)
and [comparison promotion requirements](../../../../../plans/archive/2026-09-26-omr-screening-comparison.superseded.md).
Preregister eligible composition-disjoint confirmation and paired claims before
predictions, with exposure/review/training-overlap disclosures and fresh comparators:
shipped 426 plus the verified fine-tuned HOMR. Preserve rational matching,
composition aggregation, failure-zero accounting, paired statistics/Holm and the
full duration diagnostics; report conversion/stitching outcomes and pinned NED.

The screen-disjoint 343-page remainder is not wholly untouched: 207 pages had
recorded prior processing. The 135-page/44-whole-group inventory without a recorded
attempt is composer-skewed and has review/training limitations; it is not a frozen
representative holdout. [Exposure/eligibility record](../../screening/v1/stage4-evaluation/REPORT.md).
Audit and select a suitable population before authorizing confirmation; do not
infer eligibility from absence of a cached prediction.

Production gate: at least +0.03 primary F1 over verified fine-tuned HOMR with
statistical support; pitch-F1 loss at most 0.01; failure-rate and failure-penalized
OMR-NED increases at most 0.01; no demonstrated conversion/stitching corruption.
Also report versus shipped HOMR. Frozen practical eligibility remains p95 page
latency at most 2x shipped, process-tree peak RAM at most 75% of physical memory,
VRAM at most 90% and unattended local operation. The 85% system safety stop does
not relax the 75% process-memory eligibility requirement. Current evidence does
not establish the full gate.

Only after those gates and a separate user adoption decision should candidate
behavior/assets enter shipped sources. Apply the release skill and run
`powershell -ExecutionPolicy Bypass -File scripts/verify-release.ps1`, verify the
published assets and actual `dist/Sheet2Play.exe` identity/model selection, and
retain the previous shipped binary/model/settings for rollback. Until a later
release is accepted, the installed app remains on shipped 426.
