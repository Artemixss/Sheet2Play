# Phase 3 acceptance ledger

Owner: [MAIN_PLAN.md](../../../../../plans/MAIN_PLAN.md), `2026-10-06-homr-timing-465`.
2026-10-08. Phase 3 is complete with qualifications; Phase 4 remains unstarted.

“Met” records the bounded Phase 3 obligation. “Unmet/unverified” below describes
remaining readiness qualifications, not an authorization to continue repairing.

| Obligation or claim | Status | Evidence / practical consequence |
| --- | --- | --- |
| Cached three_voices first-error trace | Met | [Diagnosis](three-voices-diagnosis.md): extra A5 already raw; export/normalization preserve it |
| Cached tuplet_aligned first-error trace | Met, bounded | [Diagnosis](tuplet-aligned-diagnosis.md): bracket loss bounded between saved stages; wrong lower durations raw; native scheduler explains later onsets |
| Exact initiating crop/model cause | Unverified | No artifact distinguishes dewarp/recrop/edge cleanup or establishes causal link to duration tokens; no speculative crop repair |
| upper2/lower2 remain voices on existing staves | Met | Four-position fixture in both native exporters and actual Bridge/MIDI/controller, two staves/two voices each |
| Only demonstrated minimal research repairs | Met | One C# revision branch, original failure and repaired 32-input success; no musical exporter/normalizer patch justified |
| Missing #171/#178 behavior repaired | Not applicable | Pinned source already contains both; fixed tokens replay unchanged; no transplant |
| Representative 465 and known-correct downstream conversion/playback | Met with scope | [Runtime checks](runtime-playback.md), 32 inputs; explicit app interpreter/published Bridge, actual cache MIDI helpers/controller |
| Voices, held notes, ties, tuplets, pickups, tempo changes | Met as checks | Golden fixtures, authoritative generated sources, cached outputs, research tie diagnostics; known tie correctness failure retained |
| Exact XML vs MIDI quantization distinction | Met | Rational event traces; exact research MIDI; 480-tick app rounding measured below tick bound |
| Perfect recognition on regressions/other controls | Unmet | A5 remains extra; aligned lower durations remain wrong; perfect recognition is not a Phase 3 closure requirement |
| Independent-voice production tie correctness | Unmet, pre-existing | Six events vs four required in isolated reproducer; no restricted-parser production insertion |
| Intended installed Python dependency/import/export/conversion compatibility | Met, bounded | Both Python 3.11.9 environments satisfy nine declared package constraints, import native code, replay 12 controls; actual installed-interpreter conversion succeeds |
| Fresh installed-runtime GPU inference / candidate in launched EXE | Unverified | Not executed; requires separately admitted and authorized integration/trial |
| Complete default MusicXML import/persistent cache | Unmet | Revision branch repaired only in research; default runtime/model/cache-settings branches remain missing |
| Title-on equivalence / physical audio | Unverified | No-title profile only; calibrated 55 ms unchanged; fake output is not hardware evidence |
| Corrected and exact controls preserved | Met | All 12 generated outputs replay/normalize identically, including offset_entry, triplet_vs_duple and prior exact controls |
| Required focused/full compatibility regression | Met | 56 focused pass; full Research/Bridge 417 cases, 2 skipped, 0 failures/errors; fresh research frontend 74/74 pass |
| Frozen Phase 2, rules, weights and production sources preserved | Met | [Preservation](preservation-after.json), [audit](audit.json): 7,630 files, 98 protected/pinned entries, 38 snapshotted production source files |
| Resource safeguards / failure preservation | Met | [Job record](job-record.md), [receipts/audit](audit.json); 85% RAM/commit, 4 GiB reserve/worker, 16 processes, serial deadlines; no pressure stop; six failed receipts retained |
| New downloads, inference, training, Phase 4 or adoption | Not performed | Existing bytes/packages only; no GUI publish, installed-library write, cloud job or inference admission |

**Outcome:** Qualified **research-only 465 trial readiness**. Observed-screen
superiority remains supported; recognition and runtime boundaries prevent a
production-readiness claim. Recommend that Phase 4 decide whether to retain shipped
HOMR or approve a bounded no-title 465 trial/integration plan. Do not automatically
start that decision phase, a trial, the shipped-repair fallback or production adoption.
