# Phase 1 — actual shipped baseline and playback boundary

Owner: [MAIN_PLAN.md](../../../../../plans/MAIN_PLAN.md), plan
`2026-10-06-homr-timing-465`. Execution: 2026-10-07. **Partial; resource-stopped.**
Only Phase 1 was authorized. Phase 2 has not started.

Runtime identity, known-correct conversion/playback fixtures and eight development
controls are verified. Native inference encountered allocation failures before
the remaining usable traces could be obtained. Preserve this partial result;
it does not establish Phase 2 readiness or a model ranking.

## Identity and inputs

[Runtime inventory](runtime-inventory.json) pins the installed executable and
Bridge, resolved Python 3.11.9 at `Bridge/.venv-homr-gpu/Scripts/python.exe`,
import origins, ordered vocabulary, configuration, tokenizers and active weights.
Identity: `e61db08610fe9b475d42a822a9ea265fed780e095758944b71cb2c0b17b0ec66`.
HOMR metadata is `0.7.0.post38+457e7c6`; installation provenance names
`457e7c6518a10ba755db2e60883419e56c4d7369`. Bytes, rather than that label,
identify this baseline. Active weights are encoder/decoder 426 FP16 and
segmentation 308 FP16; CUDA is forced, PDF default 300 DPI, BPM fallback 120.

[Patch inventory](patch-inventory.json) records the custom measure voice planner,
its function hashes, positive-duration guards and diagnostic tuplet switch.
Exporter SHA256 is `c01415ed218a29326e207b9c21c9ff46fa6b2403c02e90f0b8e73399ac7afd83`.
The planner attempts repairs when grouped duration differs from expected meter;
it does not repair every ambiguous overlapping stream. `_advance_to_next_group`
and `split_mixed_chords` are absent. No source update was fetched. Installed HOMR
source matches the local vendor comparator, which is not proven original release
bytes. `SHEET2PLAY_HOMR_KEEP_TUPLETS` was absent; cleanup remained enabled.

[Eligibility ledger](reference-eligibility.json): all 12 generated controls and
20 OpenScore first-page inputs/reference files match the frozen development audit.
Generated references come from paired authoritative MusicXML/kern, never a
predicted-token reconstruction. OpenScore whole-composition references have
unverified first-page ranges and possible training overlap: diagnostic use only,
with no numerical accuracy claims or reference-based alignment.

## Known-correct conversion, MIDI and playback

[Final research/Bridge regression](regression-final.xml): **392 passed, 2 skipped**,
zero failures/errors. [Fresh frontend build/test](playback-results/phase1-frontend.trx):
**69 passed**. Coverage includes overlapping same-pitch notes, independent voices,
dotted/tied notes, tuplets, pickup/page offsets, tempo changes, seek/note scheduling
and tempo-aware MIDI round trips. Eight authoritative control MIDI round trips
preserved exact pitch/onset/duration multiplicity at 10,080 ticks per quarter.

[Independent-voice tie boundary](tie-boundary.json): expected exact events in
quarter beats are `(55,0,1/3)`, `(60,0,1)`, `(62,1,7/3)`, `(64,0,1)`.
The bounded research parser and MIDI retain these four; production normalization
still produces six. Production timed events are retained in that artifact.
No restricted research parser was substituted into production.

Production SongCache exports MIDI at 480 ticks per quarter: septuplet fractions
cannot be represented exactly at that resolution. Research MIDI verification
therefore does not establish exact production preservation for those fractions.
Tests do not verify physical audio calibration or installed-executable playback;
the calibrated audio offset, shipped sources and published assets were unchanged.

## Development failure traces

Native shipped page processing captured images, detection/debug artifacts, staff
crops, pre-cleanup decoder symbols, later exporter inputs, MusicXML and normalized
events. Diagnostic/debug switches changed artifact capture, not musical returns.
[Analysis](development-analysis.json) verifies declared hashes and compares exact
pitch/onset/duration events without time warping. [Detailed traces](failure-traces.json)
link source/crop/token/XML hashes and first-measure missing/extra events.

| Control completed before resource failure | Exact event F1 | First divergent measure / earliest demonstrated stage |
| --- | ---: | --- |
| baseline-piano-001 | 1.0000 | None |
| homophonic | 1.0000 | None |
| three_voices | 1.0000 | None |
| offset_entry | 0.4286 | 1; onset placement in MusicXML, token voice representation remains ambiguous |
| quintuplet_vs_duple | 0.3750 | 1; decoder output lacks tuplet rhythm and notes |
| septuplet_vs_duple | 0.0909 | 1; decoder output has ordinary quarters and incorrect meter |
| syncopation | 0.1250 | 1; decoder meter/voice representation, then serialized XML onsets |
| same_position_sustain | 0.0000 | 1; staff crop loses low ledger-line unison notes |

The syncopation source hides its initial eighth rest (`print-object=no`); absent
rest tokens do not prove rest recognition failure. Reference durations of its
pitched notes are retained, while voice onset reconstruction fails. Crop margins
also clip stem/tempo details. Decoder-stage findings do not rule out earlier
visual degradation; detector causality and exporter-only causality are unverified.

Duration diagnostics are conditional on **81 exact pitch/onset pairs** in these
eight controls, not a composition-level accuracy result. Rows are reference,
columns predicted; quarter-beat labels follow the same order:

| Duration | 4/7 | 4/5 | 1 | 3/2 | 2 | 4 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 4/7 | 0 | 0 | 1 | 0 | 0 | 0 |
| 4/5 | 0 | 0 | 1 | 0 | 0 | 0 |
| 1 | 0 | 0 | 59 | 0 | 0 | 0 |
| 3/2 | 0 | 0 | 0 | 1 | 0 | 0 |
| 2 | 0 | 0 | 0 | 0 | 18 | 0 |
| 4 | 0 | 0 | 0 | 0 | 0 | 1 |

Majority baseline accuracy **0.7284**, balanced accuracy **0.6667**, macro-F1
**0.6639**. Predictions are not single-class. The pairing condition excludes
onset/pitch errors, so these diagnostics cannot replace transcription metrics.

## Resource stop, containment and network budget

[Job record](job-record.md) and per-job receipts preserve commands, configuration,
process IDs, limits, telemetry and logs. Every substantive CPU job used the
existing guarded supervisor: 85% RAM/commit stops, 4 GiB reserve and aggregate
worker cap, 16 processes, one worker and deadlines. GPU admission found 6,141 MiB
total, zero used, no compute application; separate two-second pressure monitoring
was active. No competing training or Git operation was launched.

The first native resource failure was RapidOCR/ONNX MaxPool `bad allocation` at
`generated-tie_across_barline`; `generated-tuplet_aligned` also failed. All 20
OpenScore pages then failed NumPy allocation. There are 32 receipts: ten XML
successes and 22 failures. Only eight controls preceded the first error. Later
triplet-vs-duple/quadruple XML successes are quarantined; no accuracy claim uses them.

The executed launcher incorrectly continued after the first allocation error.
[Executed source snapshots](executed-source/homr_baseline_infer.py) and all failed
receipts are retained. The corrected research launcher stops before the next item,
records the failure and refuses implicit resume; a mocked native batch verifies
this behavior. No further inference was attempted. System RAM peaked at 70.05%,
commit at 55.61%; the system pressure gate did not trigger and containment closed
cleanly. The precise allocator/worker-quota cause remains unverified.

Initial .NET test-host quota refusal and a subsequent PowerShell argument error
are also preserved. The successful current-source build used serial MSBuild,
no restore/compiler server/node reuse, two visible CPUs and a 256 MiB GC bound.
The earlier cached-DLL check is not the fresh-build acceptance evidence.

The hard task network limit was **2,000,000,000 bytes**. No research network
transfer, source/weight download, installation, upload or cloud job was requested.
Python children inherited a socket/name-resolution block; .NET used no restore
and telemetry opt-out. [Network/process closeout](network-closeout.json) records
zero requested research transfers. Wi-Fi counters reset during the session, so
adapter endpoints cannot prove a total for unrelated host traffic; no host-wide
firewall/accounting claim is made. This task required zero external artifact bytes.

## Acceptance and remaining work

[Verified closeout](closeout.json): 56 protected runtime artifacts unchanged,
362 declared inference artifacts verified, all 32 receipts retained. No owned
worker/root lock remained at the final process inspection.

| Acceptance item | Result |
| --- | --- |
| Actual baseline identity and patch inventory | Met, with original-release provenance qualification |
| Development input/reference identity | Met for all 32; OpenScore page-range eligibility unresolved |
| Known-correct conversion/playback boundary | Met for deterministic tests; physical audio unverified |
| Independent-voice tie limitation retained | Met; four reference versus six production events |
| Complete development traces | Partial; eight before resource failure, 24 need recovery/review |
| Phase 2 readiness | Not established; Phase 2 not authorized or started |

Next action remains Phase 1: review allocation receipts and containment constraints
before an explicitly resumed execution with fresh evidence paths. Recover two
failed and two quarantined generated controls and all 20 OpenScore page traces;
independently verify first-page reference ranges before numerical claims. Keep
resource safeguards and the execution's network cap; preserve historical evidence.
No automatic retry, source/weight replacement, training or promotion is pending.
