# Phase 2 — Pinned upstream HOMR 465

**Owner:** [MAIN_PLAN.md](../../../../../plans/MAIN_PLAN.md),
`2026-10-06-homr-timing-465`.
**Completed:** 2026-10-08, Europe/Istanbul.
**Acceptance:** Complete with qualifications. Phase 2 only; Phases 3–4 unstarted.

The pinned 465 bundle has a supported primary-F1 advantage over the fresh
shipped-source control on the previously observed 59-page screen. It also regresses
two generated development measures. Neither untouched-data generalization nor
production readiness is established. No shipped source/weight replacement,
training, cloud execution, publishing or promotion occurred.

## Identity and admission

Candidate `homr-465-upstream` uses source
`33baa326900faa12702df8c4bdcbea034a3d6a34` and matching FP16 encoder/decoder
`465-597144cab54c8f6d0f6c9619df5c5312694eadd6`. Source, archives and extracted
models are isolated under `Research/omr/.runtime/homr-465-upstream`.
Fresh official release metadata, archive digests and model/source hashes are in
[acquisition.json](acquisition.json). The final audit reverified all three archives,
the active source inventory and model hashes.

The separate [465 contract](../../../homr_465_contract.json) verifies ordered
vocabularies, pad/BOS/EOS/nonote IDs, all six output heads and complete ONNX
interfaces. Position order is `., upper, upper2, lower, lower2`; its width is five,
compared with three in the preserved 455 contract. Other vocabulary orders and
interface types/shapes match the checked historical contract. An initial wrong
position-order expectation was rejected and corrected before admission; its
failed receipt remains. Native admission and subsequent reverification passed:
[created contract evidence](compatibility-created.json),
[verified contract evidence](compatibility-verified.json).

Both profiles use the same existing research runtime, CUDA provider, eight intra-op
threads, one inter-op thread and pinned segmentation weights. Native page detection,
crops, decoding and XML export are retained. Actual import origins, all three ONNX
sessions, provider/thread settings and artifacts were verified for every receipt.
The control uses installed patched HOMR 426 source/weights with baseline identity
`e61db08610fe9b475d42a822a9ea265fed780e095758944b71cb2c0b17b0ec66`.
This is a fresh shipped-source/weights control in a shared research runtime;
it does not claim equivalence to every dependency of the installed app.

Both profiles use native `title_detection=false`, retaining the Phase 1 title-OCR
qualification. General title-profile musical equivalence is not established.
The installed production normalizer is unchanged, including its known independent-
voice tie limitation. The 465 result evaluates a source/weights/pipeline bundle;
it does not attribute a gain to weights alone.

## Development evidence

Both required probes passed, followed by all 32 native development captures:
12 generated controls and 20 first-page OpenScore diagnostics. No native failure
or resource stop occurred. Saved evidence includes page/crop images, staff positions,
raw decoder outputs, cleaned exporter inputs, XML, timed events and resources.

[Development analysis](development-analysis.json) and
[development review](development-review.md) preserve all results. Generated-control
mean primary F1 is 0.6096882692, a descriptive item mean. Two measures become exact
(`offset_entry`, `triplet_vs_duple`); two previously exact measures regress
(`three_voices`, `tuplet_aligned`). The aligned-tuplet control drops from 1.0 to
0.125, with a duration discrepancy already present in decoded tokens. No tuning
or repair followed these observations. OpenScore remains diagnostic only, with
no numerical accuracy claim.

## Frozen comparison

[Freeze](comparison-freeze.json) identity:
`91e7256cd902a6ea2adb9fb415e6847b2ba0b9e94fb03fe8f5f1570ae6544fb9`.
It pins profiles, the unchanged 59-page/18-composition sample, authoritative
reference/input hashes, production normalizer, scoring/helper code, settings,
hardware/provider evidence and one superiority claim before the first capture.
No tuning used the 59-page results. Both engines were captured afresh, alternating
engine order per page. Original screening/evaluation identities remain untouched.

All 118 result/score pairs are present. The candidate has 59 usable XML conversions;
the control has 58 and one native exporter assertion. Control item
`e2139c49a0b38b5921a9` (`beethoven/sonata17_1/sonata17_1_6.png`) failed the
positive-duration assertion in `build_note_chord`. Its tokens, traceback and
resources remain; all three F1 scores are zero under the frozen failure policy.
It was not retried or repaired. There are no unresolved resource-stopped captures.

Composition-macro metrics, including failure-zero pages:

| Metric | Pinned 465 | Shipped-source control |
| --- | ---: | ---: |
| Primary pitch/onset/duration F1 | 0.5313290603 | 0.4139483028 |
| Pitch/onset F1 | 0.5530193830 | 0.4374030143 |
| Pitch F1 | 0.9796934040 | 0.9700843734 |
| Missing exact pitch/onset/duration events | 11,139 | 14,658 |
| Extra exact pitch/onset/duration events | 11,325 | 14,289 |
| Complete reference chords / 5,894 | 2,861 | 1,860 |

The primary difference is **+0.1173807575**. The paired composition bootstrap
95% interval is **[0.0240277078, 0.2202143270]**, seed 20261007, 10,000 resamples.
Exact paired composition label swaps enumerate 262,144 assignments:
one-sided superiority p = **0.0174827576**. Holm adjustment for the single frozen
claim is the same value. Both predeclared support conditions pass. Twelve
composition differences are positive and six negative. This is a supported
observed-screen gain, not an untouched confirmation or a universal improvement.

[Complete report](comparison-report.json) contains every page score, exact counts,
staff coverage and chord completeness. Staff indices are notation indices, not
validated hand labels. Human correction time was not measured.

Conditional duration diagnostics:

| Diagnostic | Pinned 465 | Control |
| --- | ---: | ---: |
| Exact pitch/onset-paired notes | 11,271 | 7,734 |
| Majority baseline accuracy | 0.4048442907 | 0.4628911301 |
| Balanced accuracy | 0.5770380376 | 0.6251687800 |
| Macro-F1 | 0.5785876442 | 0.6099289756 |
| Single-class predictor | False | False |

The full ordered confusion matrices are in the complete report. These diagnostics
condition on different sets of matched notes and do not replace primary F1 or
establish that 465 is a better duration classifier in isolation.

## Interruption, RAM and runtime

Original session 72555 stopped on control item 47 at a supervisor deadline.
Samples have a 3,632.943356-second gap; recorded peaks were 71.4873% physical RAM
and 55.9912% system commit. The initiating cause is unverified; there is no recorded
RAM/commit-pressure stop. The original guarded receipt/log and 42 partial capture
files remain, with their hashes independently verified after preservation.
The user's continuation authorized a reviewed fresh attempt, which succeeded;
session 20156 completed the remaining 12 pairs without another resource stop.
See [job record](job-record.md) and
[resumption admission](resumption-admission-20261008.json).

After the reported 16-to-32 GB upgrade, Windows detects 33,549,094,912 usable physical
bytes (31.25 GiB). There is no active 16 GB physical-memory ceiling. Percentage
admission automatically uses detected capacity. Mandatory 85% RAM/commit stops,
4 GiB reserve, 4 GiB aggregate worker allowance, 16-process containment, 600-second
capture deadlines and the four-hour session boundary remain. GPU admission is
separate: the same RTX 4050 Laptop GPU UUID/driver and 6,141 MiB VRAM were verified,
with a 90% stop and 1,569 MiB observed peak.

Native capture timing is descriptive; RAM cohorts are separate:

| Cohort | Successful matched pairs | Candidate mean / median seconds | Control mean / median seconds |
| --- | ---: | ---: | ---: |
| Before reported RAM upgrade | 45 of 46 | 15.6904 / 15.9530 | 15.5420 / 15.7340 |
| After RAM admission | 12 of 12 | 15.6509 / 14.8045 | 15.0261 / 14.3825 |

The page spanning the transition is excluded from matched performance claims.
The complete report preserves pooled elapsed times for reproducibility, but they
are not a uniform-hardware benchmark. Background load, thermals and different page
mixes prevent attributing cohort timing differences to the RAM upgrade. No causal
speedup or complete installed-app runtime claim is made.

## Network and verification

The hard execution cap is **3,000,000,000 bytes**. The
[budget](network-budget.json) reserved **804,216,858 bytes**, including conservative
protocol/control and failed-request allowances. Completed response payload is
113,959,839 bytes; retained interrupted bytes are 5,308,416, for **119,268,255 bytes**
of retained payload. Charged payload upper bound is 200,512,129 bytes. The ledger's
interrupted-byte counter lagged the preserved file by one 65,536-byte chunk; the
audit uses actual file size, while the full failed-request reservation already
covers it. Failed download/journal receipts remain. No further downloads or package
installations occurred; native inference and scoring used the offline gate.
Accounting covers task-controlled transfers with conservative reservations;
unrelated host traffic is unavailable.

Seventeen focused compatibility/network/analysis fixtures passed. The full relevant
research/Bridge regression records **417 cases, two skipped, zero failures/errors**:
[JUnit](full-regression.xml). Its SHA-256 is
`fd455cd11b2fa83f5c6cc0c68a453b002d22d3d7dba88050a577de8cacf073a2`.
[Final audit](audit.json) verified 150 native receipts (149 complete, one failed),
6,608 declared capture artifacts, 51 protected runtime/455-contract artifacts,
three acquisition archives and 42 preserved interrupted artifacts. It regenerated
all 118 scores/timed-event sets and reproduced composition macros, bootstrap,
exact label swaps and Holm results. The actual scoring interpreter, NumPy 2.2.6
and normalizer origin/hash were recorded before scoring in
[scoring-environment.json](scoring-environment.json). Capture dependencies and
their actual native import/provider evidence were separately checked.

Sandbox file/link/rename and diagnostic-import failures remain preserved. Offline
normalizer analysis required approved canonical-path access. The shared inference
environment lacks `psutil`; diagnostics run in the existing research interpreter
and verify the pinned inference environment's package metadata without installing
anything. Frozen scoring/capture helpers were not changed after comparison began.

## Acceptance and next action

| Phase 2 criterion | Acceptance evidence |
| --- | --- |
| Isolated, compatible, reproducible candidate | Official digests, independent 465 contract, native admissions and fresh source/model/import/provider audit |
| Required probes and complete development | 32 complete captures, all timed events, scored generated controls and diagnostic-only OpenScore traces |
| Frozen fresh comparison | 59 pages/18 compositions per engine, one explicit failure, 118 scores, preserved frozen identities and failure-zero policy |
| Reproducible scoring without screen tuning | Full regenerated scores/statistics match; frozen source/config hashes unchanged |
| Resources, network, protected runtime | Supervised receipts, reviewed interruption, fresh RAM/GPU admission, budget under 3 GB, protected hashes verified |
| Relevant validation | 17 focused fixtures and complete regression pass; no worker/lock remains |

Phase 2 is complete with the limitations above. Review its supported screen gain
and generated musical regressions before selecting conditional Phase 3 repairs or
Phase 4 recommendation work. Either requires a separate execution request. No
later phase or production promotion is started by this closeout.
