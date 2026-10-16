# Fine-tune export verification job

**Status:** Completed Phases 1–4, 2026-09-28, including the later authorized
screening and HOMR-only analysis. [Archived completed plan](../../../../../plans/archive/2026-09-28-homr-finetune-export-repair.done.md);
[plans/status index](../../../../../plans/README.md). The original repair-only
stop and zero-screening statements below are history; the subsequent
Phase 4 completion section records their resolution. No rerun is required.

Scope selected 2026-09-28: Phases 1–3 of [the repair plan](../../../../../plans/archive/2026-09-28-homr-finetune-export-repair.done.md). Stop before Phase 4 screening. No training or production changes.

Local working directory: `C:\Users\bur4x\Desktop\lecture\big_projects\Sheet2Play`.
Remote chat: `01a0a9eb-4674-7342-aecd-0c437ad6704a`, host `remote-control:env_e_6aaa7759fbb4832ab2323945df4f2a2c`.
Existing checkpoint: `checkpoint-135674/model.safetensors`, SHA-256 `bb077e964069145996376c209a035a473986c255143e73e8777bfbbf908a6de0`.
Existing encoder: `7e60796fc1b8702008eabda3c0b737daffa80984d34749edec26b162fda596d5`.
Existing decoder: `54c4940a2c8f8ca2c340744f29ea6a90a1645973ee7195d127d1b2c776609fce`.

## Initial state

- Plan existed in this chat but had not been saved. Saved approved phase boundaries before execution.
- Previous remote audit completed; source checkpoint exists, final remote/release/local bytes match, and old manifest decoder hash differs.
- No new worker was launched locally. Sandboxed CIM process query was denied; recheck via psutil before any local job.
- Phase 1/2 remote work will record exact commands, inputs, logs, process identity, and resumable state in the private report repository before long verification.
- Phase 3 remains gated on transferred, verified Phase 2 evidence. No frozen evaluation inference is authorized.

## Historical transport stop — 2026-09-28 (resolved below)

- User explicitly approved transferring HOMR source/patches, tokenizer/config files, and export verification reports/scripts to private `Artemixss/report`, excluding credentials, private music, datasets, and optimizer state. Read-only `gh repo view` confirmed `isPrivate=true` and `viewerPermission=ADMIN`. This resolves the automatic-review transfer rejection; the problem now is remote connectivity.
- Remote verification request and subsequent transfer authorization were successfully dispatched to the existing chat. Its current turn/process status cannot be retrieved: `wait_threads` reports the host unavailable, and `list_threads` reports `thread_list_unavailable`. Do not resend the job or assume its verification process has stopped.
- `gh api repos/Artemixss/report/contents/reports` shows the historical epoch-14 manifest/exporter but no `finetune-export-verification-v1` bundle at the current check.
- Local psutil process inventory found no pre-existing Python/WSL worker. Local preflight: 56.1% RAM, 0 MiB device-wide VRAM, approximately 59.0 GB free disk, no admission blockers.
- Development pages `openscore-6211535-page-1`, `openscore-6211549-page-1`, and `openscore-6211555-page-1` passed frozen input/reference hashes in `development_inventory()`.
- Phase 1 is incomplete: the authoritative provenance/source bundle has not arrived. Phase 2 has no retrieved checkpoint/export-equivalence result. Phase 3 has not begun. No model code, weights, historical manifest, or production runtime changed; no new local inference or frozen screening ran.

### Exact missing information/artifact

Restore remote host `remote-control:env_e_6aaa7759fbb4832ab2323945df4f2a2c`, then retrieve the latest turn and process/job state for chat `01a0a9eb-4674-7342-aecd-0c437ad6704a`. The requested bundle is `C:\Users\PC1\dev\omr-training\reports\finetune-export-verification-v1\` and, after the authorized push, private `Artemixss/report:reports/finetune-export-verification-v1/`.

It must provide strict checkpoint-load evidence; checkpoint-to-ONNX encoder, initial/cache-step, and generation verification on development music; tolerances/errors/token agreement; ordered vocabulary/interface contract; exact source/patch/config/tokenizer identities; and a new provenance manifest for the verified final binaries. A hash replacement or session-load smoke is insufficient.

### Exact next action

Check `wait_threads`/`read_thread` on the existing remote chat before starting anything. If still working, wait for its result; if interrupted, read its job record and inspect live processes before resuming. Retrieve the approved bundle from the matching private repository at its reported commit and verify every transferred hash. Continue Phase 3 only after Phase 2 passes. Stop before Phase 4.

## Resumed through the report repository — 2026-09-28

The user supplied the remote result and commit `9bf0d477aa75e8c4a7b48ad6b9fdae2d24c1fab7`. The unavailable host tool did not prove that the remote PC/chat was offline. The private report route works and supersedes the transport blocker above.

- Retrieved 29 blobs under `reports/finetune-export-verification-v1/` using GitHub's tree/blob APIs, validating Git object identity and byte count. All 28 entries in the bundle's SHA-256 inventory match. Raw bundle: `Research/omr/.runtime/finetune-verified/report-9bf0d47/`.
- Remote strict checkpoint and wrapper loads passed. CPU parity passed at atol=0.02/rtol=0.02 on a synthetic gradient and real public piano crop, including three decoder calls with caches and repeated exact greedy-generation agreement ending at EOS after 63 tokens. Remote CUDA provider failed at fused attention; CPU parity is valid independently.
- Reconstructed isolated HOMR source from local vendor Git object `457e7c6518a10ba755db2e60883419e56c4d7369` with `git archive`, then applied the verified remote patch using `git apply --directory=Research/omr/.runtime/finetune-verified/source`. Initial archive-byte differences were CRLF/LF; installed the 18 exact bundle source/tokenizer files after checking reconstructed content. No source mismatch remains.
- First patch check used the wrong working directory and failed without editing source; a second subdirectory Git invocation skipped paths. The explicit directory invocation applied the patch successfully. Originals remain unchanged.

### Planned Phase 3 commands and logs

Working directory for all local commands is the workspace root. Interpreter: `Research/omr/.venv/Scripts/python.exe`; engine interpreter: isolated research `Research/omr/.runtime/homr-455/venv/Scripts/python.exe`, with PYTHONPATH selecting the reconstructed fine-tune source.

1. Focused contracts: `Research/omr/.venv/Scripts/python.exe -m pytest Research/omr/tests/test_screening_finetune.py Research/omr/tests/test_screening_stage2.py -q -o addopts=''`.
2. Prepare: `Research/omr/.venv/Scripts/python.exe Research/omr/screening_prepare_finetune.py --bundle Research/omr/.runtime/finetune-verified/report-9bf0d47`; console log `prepare.log` beside this record. Preparation validates evidence and ONNX interfaces but runs no benchmark inference.
3. Development: `Research/omr/.venv/Scripts/python.exe Research/omr/screening_development.py --manifest <prepared-manifest> --candidate fine_tuned_homr --item-id openscore-6211535-page-1 --session-id finetune-dev-01`, then the other two fixed pages only after the first passes. Use the returned content-addressed manifest path; worker jobs record exact input/configuration, PID/creation time, command, logs, resources, raw output and resume state under the existing screening output root.
4. Admit only a passing report under that exact identity; run full research/Bridge regression and stop before Phase 4. The fine-tune launcher rejects wrong models/source and CUDA-provider fallback. No frozen screening command is part of this request.

### First complete-page attempt

Prepared manifest `manifest-v4-ef12f395cd4d.json`; configuration identity `544cf237067443623679ad057a2b84cdf9f1520be77a7aee9c4d39100ffee996`. Focused provenance/screening tests: 33 passed; existing symbolic conversion fixture: one passed.

Development session `finetune-dev-01`, attempt `2c98d5638c36/development-attempts/fine_tuned_homr/finetune-dev-01-454699ea1ecc4cc6b6da70bd9447ce51/`: 35.75 seconds, 60.2% RAM, 1563 MiB device-wide VRAM. All five detected systems executed the verified epoch-14 encoder/decoder on CUDA successfully. Output failed at conversion because the new identity guard rejected a required RapidOCR ONNX detector. This is a launcher integration defect, not the remote CUDA kernel failure or a model-quality failure. Raw logs are preserved.

Focused remedy: pin all installed RapidOCR models in runtime identity and permit precisely those auxiliary model paths/hashes; keep CUDA mandatory for the HOMR encoder, decoder, and segmentation model. Prepare a new immutable candidate/manifest identity before retrying the same fixed development page. Do not reuse or score this failed development attempt.

### Corrected identity and remaining development runs

Preparation after the auxiliary-model correction produced `reports/screening/v1/manifest-v4-6cc5a0d9d45e.json`, file SHA-256 `9063422eb4ef98fd570c9d22ad10b197d971c1d4bcd305698ace4e2665eb5e41`. Raw prepare log: `prepare-v2.log`. Candidate configuration directory: `ac952929387b`.

Representative retry command: `Research/omr/.venv/Scripts/python.exe Research/omr/screening_development.py --manifest Research/omr/reports/screening/v1/manifest-v4-6cc5a0d9d45e.json --candidate fine_tuned_homr --item-id openscore-6211535-page-1 --session-id finetune-dev-02`. It succeeded and produced `2c98d5638c36/development/fine_tuned_homr/ac952929387b/openscore-6211535-page-1.json`. Console log: `development-6211535-v2.log`.

Remaining exact commands use the same manifest/candidate and `--item-id openscore-6211549-page-1 --session-id finetune-dev-03`, then `--item-id openscore-6211555-page-1 --session-id finetune-dev-04`, sequentially. Console logs: `development-6211549.log` and `development-6211555.log`. Each parent saves PID/creation time, worker commands, resources and raw artifacts in its development-attempt directory. Stop this loop on a failed or pending result; do not repeat successful inference.

After all three pass: `Research/omr/.venv/Scripts/python.exe Research/omr/screening_admit.py --manifest Research/omr/reports/screening/v1/manifest-v4-6cc5a0d9d45e.json --candidate fine_tuned_homr --development-report Research/omr/reports/screening/v1/2c98d5638c36/development/fine_tuned_homr/ac952929387b/openscore-6211535-page-1.json`. Full regression command: `Research/omr/.venv/Scripts/python.exe -m pytest Research/omr/tests Bridge/tests -q -o addopts=''`, log `regression.log`. No inference or scoring on the 59-page frozen sample is authorized.

### Final provenance audit

The three corrected development runs succeeded and admission `admission-94b3ae062293.json` passed. Full research/Bridge regression: 213 passed, 2 skipped, 9 subtests passed; log `regression.log`.

A final audit found that candidate identity did not include `Bridge/homr_gpu.py`, `screening_homr_compatibility.py`, or `screening_homr_extension.py`, and the ambient `SHEET2PLAY_HOMR_KEEP_TUPLETS` diagnostic could alter inference. Pinned those files and explicitly disabled that override in configuration/environment. The prior successful evidence remains immutable; it is superseded for future admission by the final identity.

Final preparation produced `reports/screening/v1/manifest-v4-502777eed80a.json`, SHA-256 `45e1b348da6c7e560751f8a61b6dc92ffa087b55409557d5c28d4609f2e1bc42`; log `prepare-v3.log`. A preflight helper mistakenly imported a nonexistent, unused `resource_snapshot` symbol and exited before querying processes; removing that import is the next preflight action. Preparation itself completed without inference.

Before executing the final development jobs, check live Python/WSL processes. Commands use the workspace root and `Research/omr/.venv/Scripts/python.exe Research/omr/screening_development.py --manifest Research/omr/reports/screening/v1/manifest-v4-502777eed80a.json --candidate fine_tuned_homr`, sequentially adding:

- `--item-id openscore-6211535-page-1 --session-id finetune-dev-05`; log `development-6211535-final.log`.
- `--item-id openscore-6211549-page-1 --session-id finetune-dev-06`; log `development-6211549-final.log`.
- `--item-id openscore-6211555-page-1 --session-id finetune-dev-07`; log `development-6211555-final.log`.

Each supervisor persists process identity, inputs, exact command, progress, logs and resources in its development-attempt directory. If interrupted, inspect its session/job state and live process before resuming; do not start a duplicate. Stop on the first failure. Reissue admission only after these reports validate against the final manifest, then repeat regression for the provenance changes. Stop before Phase 4.

## Completion — Phases 1–3; stopped before Phase 4

The corrected process preflight found no prior candidate worker (the Python wrapper belonged to the preflight itself; `wslservice.exe` is the service). RAM was 52.0%. Final focused tests: 33 passed, log `focused-final.log`.

All three final development commands above completed successfully. Reports are under `reports/screening/v1/2c98d5638c36/development/fine_tuned_homr/9fa13d27f0b7/`; each has native tokens, MusicXML, canonical events, engine log and an identity sidecar. Twelve declared artifact hashes reverify. Loaded encoder, decoder, segmentation and three auxiliary OCR identities match the pinned inventory; CUDA is present for all HOMR sessions. The explicit tuplet override remained disabled. Native, MusicXML and canonical-event hashes match the prior successful identity on all three pages.

| Development page | Wall time | Peak system RAM | Peak device-wide VRAM | Outcome |
| --- | ---: | ---: | ---: | --- |
| `openscore-6211535-page-1` | 30.750 s | 61.1% | 1,563 MiB | succeeded |
| `openscore-6211549-page-1` | 30.750 s | 58.4% | 1,563 MiB | succeeded |
| `openscore-6211555-page-1` | 25.750 s | 59.3% | 1,563 MiB | succeeded |

These are development readiness checks, not accuracy or unattended screening claims. Remote CPU parity establishes checkpoint/export equivalence; remote CUDA error 9 is preserved in `../v1/finetune-export/remote-9bf0d47/verification-cuda-failure.log` and did not reproduce on this PC. Auxiliary OCR sessions use CPU as explicitly permitted.

Final identities:

- Manifest: [manifest-v4-502777eed80a.json](../v1/manifest-v4-502777eed80a.json), SHA-256 `45e1b348da6c7e560751f8a61b6dc92ffa087b55409557d5c28d4609f2e1bc42`.
- Candidate: `9fa13d27f0b7e64cbbe7c462287319f45c1ace5e1ed1b640d4dbb3e3bcd0a98f`; adapter configuration: `426183ceebd62651ac638db869fa7ea85bd49d71dda7825ebb52954c9b6029aa`.
- Admission: [admission-23d1108e5364.json](../v1/2c98d5638c36/admissions/fine_tuned_homr/9fa13d27f0b7/admission-23d1108e5364.json), SHA-256 `9e5d36cef42b3e314d5ed0789aef48dc3980ad9cdccdd8e9aab51d94f9cefbc5`.
- Local audit: [local-entry-verification.json](local-entry-verification.json), SHA-256 `4840078b01efe259a9451cbf1170ab08f670d1667ef5b51d46b1fa982949fa8b`. Its loaded-path comparison expands the existing `${WORKSPACE}` log redaction before resolving paths; the first audit helper omitted that expansion and rejected all six paths without changing any candidate evidence.
- Frozen sample: `2c98d5638c368b1a53bdb3440177d04fa585f9b1ca6ce6adbe65af64cd8e27d1`, unchanged 59 pages / 18 compositions; frozen scorer and protocol identities unchanged.

Admission command: `Research/omr/.venv/Scripts/python.exe Research/omr/screening_admit.py --manifest Research/omr/reports/screening/v1/manifest-v4-502777eed80a.json --candidate fine_tuned_homr --development-report Research/omr/reports/screening/v1/2c98d5638c36/development/fine_tuned_homr/9fa13d27f0b7/openscore-6211535-page-1.json`; log `admission-final.log`. The inference runner's admission validator and the development validator both rechecked final evidence.

Final full regression command: `Research/omr/.venv/Scripts/python.exe -m pytest Research/omr/tests Bridge/tests -q -o addopts=''`; log `regression-final.log`. **213 passed, 2 skipped, 9 subtests passed in 41.40 s**, with one expected music21 unreadable-clef fixture warning. No worker remains from these jobs.

### Historical repair-only stop and next action

Phases 1, 2 and 3 are complete; no required artifact is currently missing for development admission. **Stop before Phase 4.** There are zero fine-tune frozen screening results and no fine-tune screening score/ranking. No training, re-export, new binary transfer, cloud spending, shipped code edit, or production promotion occurred. Do not dispatch new remote work or repeat successful development inference.

Only after a new screening request: check live processes/resources, reverify the final manifest and admission above, then use this exact identity for the 59-page screen under the unchanged 90% policy. Do not use the superseded fine-tune manifests/admissions for new inference. Stop if an identity check fails and name the exact changed or missing file/hash before dependent work. The original v4 and historical results remain preserved.

Final documentation validation: all 87 local links in the updated plan/handoffs/startup/rules resolve; `git diff --check` passed. Final process check found zero live candidate workers and confirmed zero fine-tune frozen screening results.

## Subsequent authorized Phase 4 — complete, 2026-09-28

The user later requested corrected HOMR-only canonical Stage 4, resumed after a
RAM-work pause, and authorized the screening prerequisites. The earlier stop and
zero-result statements above describe the completed repair-only request. The
[Stage 4 job record](../v1/stage4-homr/job-record.md) now preserves the combined v4
manifest and fresh candidate admissions. Fine-tune configuration `4cd03e3ed82f`
completed all 59 inference outcomes successfully and all 59 verified scores, total
61.7 minutes, primary F1 0.3844. Corrected 455 and preserved shipped results are
included in the [final HOMR-only report](../v1/2c98d5638c36/reports/homr-only-stage4-e35f73ca9f75/REPORT.md).
No supported primary-F1 gain over shipped HOMR was established; keep shipped HOMR.
All sessions are closed and no worker remains. Do not repeat completed inference;
stop before Audiveris/Zeus, confirmation, training or promotion until requested.
