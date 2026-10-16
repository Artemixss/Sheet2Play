# Phase 1 bounded title-OCR unblock — complete

Owner: [MAIN_PLAN.md](../../../../../../plans/MAIN_PLAN.md), plan
`2026-10-06-homr-timing-465`; [current handoff](../../handoff.md).
The explicitly requested title-OCR unblock is complete. This closes capture and
page-boundary readiness, not all Phase 1 causal review. Phase 2 has not started.

The preserved [6212196 traceback](../resume-20261007/development/openscore-6212196/failure-traceback.txt)
failed after staff parsing, while `title_future.result(60)` awaited RapidOCR title
detection: ONNX Conv `Add.57_nchwc` bad allocation. The exact initiating allocator
cause remains unproven. HOMR already exposes `ProcessingConfig.title_detection`
and `--no-title`; disabling it supplies an empty title Future without invoking OCR.

## Separate profile and gates

[profile.json](profile.json) identifies `shipped-426-no-title-phase1` as
`a6cab9a5ac91aa7cd31be843b8cb37a189cd1bc564857dc235a82db8da054c32`.
The baseline runtime remains
`e61db08610fe9b475d42a822a9ea265fed780e095758944b71cb2c0b17b0ec66`.
The sole native configuration delta is `title_detection=false`. CUDA, 426 FP16
transcription/308 segmentation weights, images, PDF resolution, musical parsing,
tuplet cleanup and exporter arguments are unchanged. Production bytes were not edited.

Containment stayed at 85% RAM/commit stops, 4 GiB reserve, 4 GiB aggregate worker
commit, 16 processes and deadlines. Every inference used one fresh supervised
native process, separate fresh 90% GPU admission and two-second GPU monitoring.
The offline Python socket/Git gate remained active. Failed receipts were preserved;
no allocation failure occurred in this profile and no automatic retry was needed.

[Two-example equivalence](equivalence.json) passed on completed 6211535 and 6212193:
input image, native crop bytes, staff positions, raw decoder streams, cleaned exporter
streams, whole canonical XML excluding only `work-title` text, literal XML events,
measure timelines and production-normalized timed events all matched exactly.
Their event counts were 222 and 160. Tempo/directions remain inside the comparison;
only title metadata is excluded. This demonstrates equivalence on these two examples,
not every possible input.

The single supervised [6212196 probe](development/openscore-6212196/result.json)
passed before the remaining sequence was launched. Guarded elapsed time was 13.391 s;
sampled process peak private memory was 3,962,343,424 bytes, compared with the earlier
failed run's 4,306,792,448 bytes. These counters do not identify the allocator's cause
or replace the supervisor's aggregate containment contract. The largest sampled
private-memory peak across the 15 new captures was 3,973,263,360 bytes.

All [twelve later pages](sequence.json) passed: 6478624, 6479829, 6564424, 6583477,
6583512, 6583907, 6583966, 6585571, 6586675, 6622814, 6623145 and 6623221.
No further inference is pending for this unblock.

## Reference boundaries and combined evidence

The [reviewed boundary evidence](boundaries/reviewed-findings.json) resolves both
previous `X1` ambiguities using the pinned PDF's last first-page system and first
second-page system, reference note content and subsequent system numbers:

| Page | Included first-page range | Excluded second-page pickup | Independent corroboration |
| --- | --- | --- | --- |
| 6583907 | 13 XML measures, through number 12 | Unnumbered `X1`, then bar 13 | Grace-note pickup and piano rests; later systems 16/20/23/27 match XML |
| 6583966 | 17 XML measures, through number 16 | Unnumbered `X1`, then bar 17 | Second-verse pickup and piano rests; later systems 19/20/23 match XML |

The earlier automatic check compared the pickup with a later system's left-margin
number. The pickup is unnumbered; that comparison did not establish a source mismatch.
The [derived ledger](boundaries/page-correspondence.json) verifies all 20 first-page
ranges and retains all 20 exact rendered-image checks. Earlier ledgers remain unchanged.

The [combined analysis](analysis/development-analysis.json) has 32 completed inputs,
12 generated controls scored, zero current failures and zero unattempted pages.
It deliberately distinguishes 12 title-enabled generated controls, five title-enabled
OpenScore captures and 15 separately identified title-disabled OpenScore captures.
OpenScore remains diagnostic-only: page mapping does not validate annotation semantics,
tie clipping, repeat interpretation or training independence, and no accuracy score or
candidate ranking is calculated. Known conversion/playback limitations remain as
documented in the [prior report](../resume-20261007/REPORT.md).

## Validation and stop boundary

[Research/Bridge regression](regression.xml): 400 recorded cases, two skipped,
zero failures/errors. This includes profile drift rejection and an equivalence fixture
that permits title text changes but rejects a tempo change. The earlier fresh frontend
build/test (69 passing cases) remains applicable to unchanged shipped code.

[Closeout](closeout.json) verified 56 protected runtime artifacts, all 32 frozen
images/references, 362 original, 462 resumed and 734 new declared inference artifacts,
the two equivalence receipts and all page/boundary evidence. Fourteen earlier first-error
traces and every old success/failure remain intact, including the quarantined successes.
The initial boundary-preparation syntax failure is retained alongside its corrected run.

[Network/process closure](network-closeout.json) records zero requested research
transfers, no Python/dotnet/Sheet2Play process, no root lock and zero GPU memory used.
The cumulative network limit remains 2,000,000,000 bytes. All research used local bytes;
the original Wi-Fi counter reset prevents claiming a measured host-wide traffic total.

Phase 1 remains partial for independent image/crop/raw-token first-error review of ten
newly captured affected pages: 6212196, 6478624, 6479829, 6564424, 6583477, 6583512,
6583966, 6586675, 6622814 and 6623145. Their literal differences are captured, but
earliest-stage attribution is not yet established. Three other newly completed pages
have no literal timed-event difference; this is a qualified diagnostic result.

Recommendation: retain this separately identified title-disabled research profile for
bounded capture work when title metadata is unnecessary. Review the ten captured traces
offline before declaring all Phase 1 acceptance met. Do not weaken memory containment
or infer a production remedy from these successful probes. Stop here: no production
change, 465 download/admission, training or Phase 2 is authorized.
