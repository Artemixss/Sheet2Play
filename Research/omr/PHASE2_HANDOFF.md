# Phase 2 OMR comparison handoff

**Lifecycle update, 2026-10-04:** Completed historical comparison Phase 2; later Phase 2R/correction records supplement it.
[Plans/status index](../../plans/README.md) identifies the owning historical
plan and its successor. Current research phases belong to [the main plan](../../plans/MAIN_PLAN.md);
dated next-step/stop statements below do not authorize new execution.

> Historical Phase-2 completion record. The expanded plan's Phase 2R was executed
> with candidate-level readiness failures; see the [completed Phase 2R handoff](PHASE2R_HANDOFF.md)
> and its job record. The
> [interruption handoff](PHASE2R_INTERRUPTION_HANDOFF.md) remains resume history.
> Its separate development audits do not amend or overwrite the frozen report below.

## Governing plan and stop state

Read the [canonical comparison plan](../../plans/archive/2026-09-26-omr-screening-comparison.superseded.md), the
[Phase 1 handoff](PHASE1_HANDOFF.md), and this handoff together. Phase 2 completed and
passed on 2026-09-18. Phase 3 has not started: no SMB, OLiMPiC, or local-diagnostic
candidate inference, checkpoint selection, ranking, promotion, or new training run occurred.

The machine-readable stop state is
[phase2-report.json](reports/phase2/phase2-report.json), SHA-256
`bf682bfd73ac201b2509938d720acfce2a823eae2456e7e2bc895feb18b5edd8`.

## Phase-2 task breakdown and result

| Work item | Result | Evidence |
| --- | --- | --- |
| P2.1 Protect the Phase-1 freeze | Passed | All 15 Phase-1 artifact hashes match; `phase1-report.json` remains `96266247b0ed475f7a9dfec8248d813cb867ba7a16c6f56e00c321b3de93b211`. |
| P2.2 Implement the neutral contract | Passed | `adapter_contract.py` validates frozen configuration, input hashes, typed status, native/MusicXML/canonical artifacts, warnings, timings, RAM/VRAM, exit status, and provenance. |
| P2.3 Add adapters in order | Passed | Shipped HOMR first, then upstream Zeus, Zeus app integration, LEGATO, and Audiveris. Completed fine-tune and PR #156 remain explicit unavailable entries. |
| P2.4 Execute the frozen fixtures | Passed | All 14 contract cases passed; see [fixture-report.json](reports/phase2/fixture-report.json). |
| P2.5 Run development-only smokes | Passed | HOMR, upstream Zeus, and full-page Zeus integration succeeded with raw stage artifacts. LEGATO and Audiveris were recorded unavailable. |
| P2.6 Audit scope and stop | Passed | Evaluation inference counts are zero for SMB, OLiMPiC, and local diagnostics; `phase_3_started` is `false`. |

The [adapter manifest](reports/phase2/adapter-manifest.json) pins source, checkpoint,
configuration, and adapter implementation revisions. The
[plan checklist](reports/phase2/phase2-plan-checklist.json) records the phase-boundary audit.

## Adapter verification

| Adapter | Development path | Result | Cold elapsed | Peak RAM | Peak VRAM |
| --- | --- | --- | ---: | ---: | ---: |
| Shipped HOMR | Annotated generated crop | Succeeded | 9.64 s | 1.45 GiB | 2.52 GiB |
| Zeus upstream | Same annotated generated crop | Succeeded | 18.39 s | 490 MiB | 1021 MiB |
| Zeus app integration | Open-development full page | Succeeded | 89.10 s | 1.02 GiB | 2.10 GiB |
| LEGATO dedicated checkpoint | Open-development full page | Unavailable | — | — | — |
| Audiveris 5.11.0 unattended | Open-development full page | Unavailable | — | — | — |

Windows WDDM did not expose per-process VRAM through `nvidia-smi`; the recorded VRAM values
are device-wide peaks sampled during isolated runs and are labeled as such in every result.
They verify measurement plumbing but are not eligible performance rankings.

LEGATO is pinned to source `179c228d3d5f67113cf739b44891b3abe046f1dc` and dedicated
checkpoint `2d07c5d0e73186f2c0b12e35ea187bbc30dec18c`. Its isolated Python 3.12
runtime, gated checkpoint access, and MuseScore converter are not installed locally.
Audiveris is pinned to release 5.11.0 / `9e1e55cd2746037d059345881c53e6a6754bffbd`
and is not installed locally. Both execution branches are covered with synthetic runtime tests;
neither is represented as an inference result.

The completed HOMR fine-tune was not verified or selected. HOMR PR #156 source is pinned at
`43e68c284c0410413d95ec8b4619fd9b9421360f`, but compatible run-445 weights remain
unavailable. Both are “not evaluated,” never guessed results.

## Zeus integration defect found and repaired

The first full-page development smoke failed before recognition because
`Bridge/detect_systems.py` used HOMR's obsolete `ProcessingConfig` signature and four-value
return shape. The controlled failure justified the minimal integration repair:
`title_detection=False` is now explicit and the current five-value return is unpacked.

The repaired path passed the same development smoke and preserves per-system native LMX,
pre-normalization MusicXML, stitched MusicXML, canonical events, timings, resource samples,
warnings, exit status, and complete provenance. This is integration validation, not evidence
that Zeus is more accurate than HOMR.

## Frozen fixture execution

All required cases passed: identical score, omitted note, inserted note, shifted onsets,
tied versus sustained equivalent, overlapping voices, tuplets, pickup, meter change, repeats,
empty output, malformed XML, missing middle system, and the source-MusicXML-to-app control.
Failures remain failure-penalized; repeats stay unexpanded for printed-page scoring; rational
quarter-note time and tie merging match the frozen Phase-1 protocol.

## Reproducibility and validation

Reproduce the Phase-2 evidence with:

```powershell
Research\omr\.venv\Scripts\python.exe Research\omr\phase2.py --execute-inference
Research\omr\.venv\Scripts\python.exe -m pytest Bridge/tests Research/omr/tests -q
powershell -ExecutionPolicy Bypass -File scripts\verify-release.ps1
```

Validation completed:

```text
Python research + bridge: 113 collected, 111 passed, 2 expected skips, 0 failed
Frozen fixture matrix:    14 passed, 0 failed
Development adapters:     3 succeeded, 2 unavailable, 0 failed
.NET release suite:       69 passed, 0 skipped, 0 failed
Phase-1 artifact audit:   0 hash mismatches
git diff --check:         passed
```

Release-gate results: lock check, tests, clean publish, 13/13 declared assets, 3/3
runtime-referenced assets, and published-app launch all passed. Verified runtime artifacts:

```text
dist\Sheet2Play.exe
SHA-256 715d6dde5281e6c8b9f016a2e57dd8cc20f203705080bcae6228021e0d595319

dist\Bridge\detect_systems.py
SHA-256 b1aac6372d1cbce32dc8e00a7e6c6d809cb9d6eb1fb82ad382cfb42a8b2e6c86
```

Launch evidence: `dist\_verify\launch.png`.

Key Phase-2 artifact hashes:

- `adapter-manifest.json`: `ce8678292805a0e1e596f6242d117458ef161b0ecbbe6f83c3a178468e673d24`
- `fixture-report.json`: `59056e4fac420dee9605e6ec2f1507d31da7e660ea54d1e7faa03c3809841d58`
- `phase2-plan-checklist.json`: `df9e088b9e2a0637a1a06453a194ba738d4b2885eff37307e24389b11f7c21bc`

## Historical next-work note (superseded by Phase 2R)

The expanded amendment inserted Phase 2R before Phase 3. See the active
[Phase 2R handoff](PHASE2R_HANDOFF.md) for current readiness and candidate exclusions.
Phase 3 still requires a new explicit request and is the frozen pretrained comparison:

1. Recheck usage and revalidate the Phase-1 freeze plus this Phase-2 adapter manifest.
2. Install/verify missing candidate runtimes without changing frozen scoring or evaluation inputs.
3. Freeze any development-selected inference settings before candidate evaluation.
4. Run the same eligible frozen items for every available engine, preserve failures as zero primary
   F1, and produce paired composition-grouped statistics from the frozen protocol.

Stop here. Phase 2 does not authorize Phase 3 inference, fine-tuned checkpoint evaluation,
rankings, recommendation, promotion, or training.
