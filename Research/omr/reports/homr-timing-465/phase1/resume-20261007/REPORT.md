# Phase 1 explicit resumption — partial, resource-stopped

**Owner:** [MAIN_PLAN.md](../../../../../../plans/MAIN_PLAN.md), plan
`2026-10-06-homr-timing-465`. **Date:** 2026-10-07. **Phase 2:** not started.
The user requested the remaining Phase 1 work after the
[original stop](../REPORT.md). This report records the new execution; the original
receipts, quarantined outputs and closeout remain preserved.

All **12 generated controls** now have usable native captures, authoritative
reference comparisons and exact reference-MIDI checks. **7/20 OpenScore first
pages** have native captures and first-error traces. A fresh-process RapidOCR
allocation failure stopped the remaining sequence: one failed page and twelve
unattempted pages. Phase 1 acceptance remains **partial**, not Phase 2 readiness.

## Runtime, safeguards and resource stop

The baseline runtime identity is unchanged:
`e61db08610fe9b475d42a822a9ea265fed780e095758944b71cb2c0b17b0ec66`.
The installed Bridge resolves the existing Python/HOMR environment with 426 FP16
transcription and 308 FP16 segmentation weights; no production/model/image-size
or recognition-setting change was made. The
[original runtime](../runtime-inventory.json) and [patch inventory](../patch-inventory.json)
pin the actual bytes and custom exporter behavior. New read-only memory telemetry
records the interpreter/import origin and detection/parsing peaks.

Each new page ran in a fresh, supervised process with unchanged 85% RAM/commit
stops, 4 GiB reserve and aggregate worker cap, 16-process limit, deadlines and
separate fresh GPU admission/monitoring. All four remaining generated controls
and the first seven OpenScore pages completed. The
[6212196 job](jobs/openscore-6212196/result.json) then failed in RapidOCR's
`Conv Add.57_nchwc` with bad allocation; its
[worker log](jobs/openscore-6212196/worker.log) and
[native receipt](development/openscore-6212196/result.json) are retained.

Peak system RAM was 67.47%, commit 55.59%; recorded process peak private memory
was 4,306,792,448 bytes, near the supervisor's unchanged 4,294,967,296-byte cap.
These counters do not prove the initiating allocator cause. NULL Job telemetry
may describe an outer Job; the supervisor receipt pins actual containment.
Process isolation improved completion but did not eliminate the failure, so the
previous retained-allocation hypothesis is insufficient. No inference retry is
pending and the sequence stopped on this first new allocation failure.

## Reference eligibility and measured controls

All 32 frozen input/reference hashes were checked again. Fresh 300-DPI first-page
renders of all 20 pinned PDFs match the frozen inference images pixel for pixel.
The [page ledger](page-font-reviewed/page-correspondence.json) verifies 18 first-page
MusicXML ranges against PDF system labels and the next page's first measure.
Two remain unresolved: 6583907 and 6583966 begin the next XML page at `X1`, whereas
the PDF starts at numbered measures 16 and 19. These need independent measure
mapping. Original MSCX pagination differs from the exported PDF and is not a
first-page oracle.

All seven completed OpenScore captures have verified page ranges. Their literal
first-page comparisons remain diagnostic-only: clipped ties, repeat semantics,
source annotation limitations and possible training overlap prevent an accuracy
or model-ranking claim. No whole-composition reference was scored against a
first-page prediction.

The [combined analysis](analysis-reviewed/development-analysis.json) reuses only
the original eight pre-failure controls plus fresh captures; two original late
successes remain quarantined. Generated pitch/onset/duration F1 is:

| Control | F1 |
| --- | ---: |
| baseline-piano-001 | 1.0000 |
| homophonic | 1.0000 |
| three_voices | 1.0000 |
| tie_across_barline | 1.0000 |
| tuplet_aligned | 1.0000 |
| offset_entry | 0.4286 |
| quintuplet_vs_duple | 0.3750 |
| triplet_vs_quadruple | 0.2857 |
| triplet_vs_duple | 0.2000 |
| syncopation | 0.1250 |
| septuplet_vs_duple | 0.0909 |
| same_position_sustain | 0.0000 |

These small development fixtures establish specific behavior, not a corpus
ranking. All twelve authoritative reference MIDIs reproduce exact expected
quarter-beat events. Existing playback/conversion evidence and production tie
limitations remain as documented in the original report: the independent-voice
tie fixture yields six production events versus four correct events; production
480-TPQ MIDI cannot exactly encode sevenths. No parser replacement, physical audio
calibration or installed-binary playback claim is made.

Duration classification is conditional on 113 exact pitch/onset pairs, excluding
unmatched notes. Majority baseline is 0.5310, balanced accuracy 0.6667, macro-F1
0.6631; predictions are not single-class. Rows are reference durations and columns
are predicted durations, in quarter beats:

| Actual / predicted | 1/3 | 1/2 | 4/7 | 2/3 | 4/5 | 1 | 3/2 | 2 | 4 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1/3 | 24 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 1/2 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| 4/7 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| 2/3 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 |
| 4/5 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| 1 | 0 | 0 | 0 | 0 | 0 | 60 | 0 | 0 | 0 |
| 3/2 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 20 | 0 |
| 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |

## First-error attribution

[Fourteen failure traces](failure-traces.json) preserve source/crop/token/XML
hashes and first differing timed events: seven generated divergences and all
seven completed OpenScore pages. `Staff2Score.predict` captures pre-cleanup decoder
symbols; `exporter_inputs` captures later cleaned symbols. Neither is an
authoritative reference or a token correction target.

| New capture | First differing measure | Earliest demonstrated stage |
| --- | ---: | --- |
| triplet_vs_duple / triplet_vs_quadruple | 1 | Decoder meter and tuplet durations; visible notes/brackets retained |
| 6211535 | 14 | Decoder loses lower half-note triplet rhythm |
| 6211549 | 1 | XML onset placement; independent voice representation is ambiguous |
| 6211555 | 1 | Piano crop loses right-hand notation |
| 6211559 | 2 | XML voice discontinuity prevents cross-measure tie conversion |
| 6211561 | 1 | Piano crop omits initial notes/clefs; register errors follow |
| 6212179 | 1 | Decoder ordinary eighths instead of implicit piano triplets; wrong meter |
| 6212193 | 2 | Decoder attaches slur to separate C5 halves; conversion fuses them |

The installed model shares slur/tie vocabulary. Slur markers alone are not a
decoder defect; attachment, pitch, event order and XML voice identity determine
conversion. Crop defects are demonstrated, but their initiating geometry cause
is unverified. XML placement defects do not establish exporter-only causality.

## Validation, network and remaining work

[Research/Bridge regression](regression.xml): **396 passed, 2 skipped**, zero
failures/errors (398 JUnit cases, including nine subtests). The original fresh
serial frontend build's **69 passing tests** remain applicable because frontend
and production sources/assets are unchanged. New page-label fixtures exercise
different engraved font sizes and exclude left-margin page numbers. Failed
intermediate checks are preserved in the [job record](job-record.md).

[Closeout](closeout.json) reverified **56 protected runtime artifacts**, **362
original** and **462 resumed** declared inference artifacts, all 32 input/reference
pairs and all 20 rendered/bounded page artifacts. Executed research sources are
snapshotted under `executed-source/`. The
[process/network snapshot](network-closeout.json) records no research worker,
no root lock and zero GPU memory use. No blocked network/Git attempt was logged.

The original hard **2,000,000,000-byte** network limit remains cumulative.
**Zero research network transfers were requested**: no download, installation,
remote job or cloud spend. Offline Python socket/Git blocking remained active.
The original Wi-Fi counter reset means host-wide traffic totals cannot be proven
from adapter endpoints; unrelated app traffic is not represented as measured.

Remaining: resolve allocation refusal without weakening safeguards, then obtain
a reviewed fresh resumption for **6212196** and the twelve unattempted pages
listed in closeout; independently map the two unresolved `X1` page boundaries.
Do not retry inference automatically, start Phase 2, download 465 or alter shipped
behavior. Phase 1 acceptance stays partial until the remaining evidence exists.
