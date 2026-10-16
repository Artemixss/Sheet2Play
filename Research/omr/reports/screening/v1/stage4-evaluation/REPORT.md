# Canonical Stage 4 evaluation and decision — 2026-09-30

**Stage 4 is complete. Keep shipped HOMR. No challenger merits an accuracy-led
larger confirmation now, and no production replacement is justified.** The shipped
versus fine-tuned result remains inconclusive; resolving that comparison is an
optional future investment, not a prerequisite for retaining the installed engine.

This review uses the completed [Stage 3 report](../2c98d5638c36/reports/consolidated-stage3-836fb923bb33/REPORT.md)
and its [complete numerical evidence](../2c98d5638c36/reports/consolidated-stage3-836fb923bb33/report.json).
The unchanged screen contains 59 pages in 18 whole SMB pianoform compositions.
The [fresh evidence audit](screen-audit.json) verifies all **295 results / 295
scores / 1,257 declared artifacts**, source and summary identities, full duration
matrices, eight paired comparisons, and frozen practical checks. This review ran
no inference or new note scoring and preserved the Stage 3 report and all freezes.

## Accuracy and reliability

| Candidate | Primary F1 | Pitch/onset F1 | Pitch F1 | Failed pages | Valid-output NED | Penalized NED | Missing / extra notes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Shipped HOMR | 0.4061 | 0.4316 | 0.9701 | 1/59 | 0.3510 | 0.3620 | 14,903 / 14,534 |
| Repaired fine-tuned HOMR | 0.3844 | 0.4096 | 0.9841 | 0/59 | 0.3645 | 0.3645 | 15,434 / 15,436 |
| Corrected HOMR 455 | 0.2857 | 0.3060 | 0.9678 | 1/59 | 0.3745 | 0.3851 | 15,424 / 15,012 |
| Audiveris | 0.0986 | 0.1179 | 0.7568 | 8/59 | 0.4451 | 0.5204 | 20,159 / 17,089 |
| Neutral Zeus | 0.0228 | 0.0370 | 0.5763 | 0/59 | 0.8069 | 0.8069 | 21,375 / 23,547 |

Primary F1 is composition-macro pitch/onset/duration F1; higher is better. NED is
lower-is-better, uses the frozen notation settings and the SMB region-derived
MusicXML reference, and is not directly comparable to published native `**kern`
scores. Valid NED uses 58 / 59 / 58 / 51 / 59 pages respectively; penalized NED
retains all 59 per candidate. No score or difficult page is omitted. Sounding ties
are merged, pickups preserved, repeats unexpanded, and predictions unshifted.
OLiMPiC systems and the private document are outside these complete-page claims.

Shipped and corrected 455 each have one `HOMR_OUTPUT_MISSING:conversion` failure.
Audiveris has five recognition failures and three `AUDIVERIS_OUTPUT_INVALID`
artifact-capture failures: two ambiguous double exports and one missing export.
These codes do not establish that all three XML files were syntactically corrupt.
There are zero typed timeouts, typed empty outputs, successful empty outputs or
OMR-NED scoring errors across the five candidates. Zeus's zero failed pages
establishes output acceptance, not accurate recognition. Failed page IDs and raw
error categories remain in the linked Stage 3 JSON.

## Paired evidence and uncertainty

| Candidate minus baseline | Primary difference | Individual 95% bootstrap interval | Holm superiority p |
| --- | ---: | ---: | ---: |
| Fine-tuned minus shipped | -0.0217 | [-0.0985, 0.0415] | 1.0000 |
| 455 minus shipped | -0.1204 | [-0.2536, 0.0199] | 1.0000 |
| Audiveris minus shipped | -0.3075 | [-0.4235, -0.1955] | 1.0000 |
| Zeus minus shipped | -0.3833 | [-0.5223, -0.2525] | 1.0000 |
| Shipped minus fine-tuned | 0.0217 | [-0.0415, 0.0985] | 1.0000 |
| 455 minus fine-tuned | -0.0988 | [-0.2375, 0.0462] | 1.0000 |
| Audiveris minus fine-tuned | -0.2858 | [-0.4132, -0.1741] | 1.0000 |
| Zeus minus fine-tuned | -0.3616 | [-0.5136, -0.2297] | 1.0000 |

All eight comparisons were reproduced from saved scores: 10,000 bootstrap
resamples of the 18 composition groups, 262,144 exact paired label assignments,
and Holm adjustment across the eight one-sided superiority claims. Bootstrap
intervals are individual intervals, not simultaneous multiplicity-adjusted bounds.
Adjusted p=1 means superiority is unsupported; it does not prove equivalence or
test the opposite inferiority hypothesis. Eighteen compositions give limited
resolution for small gains. Shipped's point-estimate lead over the fine-tune is
inconclusive, and 455's lower estimate also has a zero-crossing interval.

## Duration and timeline diagnostics

| Candidate | Matched pitch/onset notes | Duration balanced accuracy | Duration macro-F1 | Majority accuracy | Majority macro-F1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Shipped HOMR | 7,551 | 0.5775 | 0.5218 | 0.4741 | 0.0238 |
| Fine-tuned HOMR | 7,000 | 0.6143 | 0.5480 | 0.4279 | 0.0214 |
| Corrected 455 | 6,957 | 0.6228 | 0.5688 | 0.3989 | 0.0204 |
| Audiveris | 2,185 | 0.3880 | 0.3521 | 0.4224 | 0.0238 |
| Neutral Zeus | 897 | 0.2340 | 0.1650 | 0.4437 | 0.0341 |

The full sparse confusion matrices and ordered labels remain in each candidate's
`duration_classification` in the Stage 3 JSON and were recalculated from saved
scores. None is a degenerate single-class predictor. Majority accuracy, balanced
accuracy and macro-F1 are different measures. These diagnostics condition on each
candidate's own pitch/onset-matched notes; better conditional duration scores for
455 or the fine-tune do not establish better overall transcription.

The [fresh audit](screen-audit.json) additionally retains every saved rational
timeline-length error and first divergent measure. The following descriptive
summaries condition on successful pages; failed pages keep their null length and
measure-1 sentinel, while headline metrics keep their failure penalties.

| Candidate | Absolute timeline error median / p95, quarter notes | First divergence at measure 1 | No divergence |
| --- | ---: | ---: | ---: |
| Shipped HOMR | 3.52 / 21.32 | 27/58 | 1/58 |
| Fine-tuned HOMR | 4.00 / 19.10 | 28/59 | 0/59 |
| Corrected 455 | 5.25 / 25.08 | 25/58 | 0/58 |
| Audiveris | 6.00 / 33.54 | 41/51 | 0/51 |
| Neutral Zeus | 11.29 / 25.42 | 59/59 | 0/59 |

These errors cannot localize the cause to recognition, representation, conversion
or stitching. No alignment, reference-guided repair or parameter selection followed
from these diagnostics, and absence of conversion/stitching corruption is unproven.

## Features, overlap and scope

All available feature breakdowns are preserved: 45/59 pages have independent
voices, 19 tuplets, 24 repeats and one a meter change; every page has ties.
Cross-staff metadata is unknown on all 59, so no cross-staff accuracy claim follows.
Feature subsets are descriptive and may share compositions; they are not separate
validated superiority claims. For example, fine-tune F1 is higher on the
independent-voice subset (0.4406 versus shipped 0.3997), while shipped is higher
on dense pages (0.2740 versus 0.1986). This does not justify choosing settings or
a routing policy from screening predictions. The one meter-change page and lack
of tie-free controls limit feature generalization.

Training overlap is **unknown for all five configurations**. Recorded fine-tune
dataset exclusions do not prove disjoint pretrained ancestry. No unseen-training
claim or full-dataset ranking is established. The incompatible historical 455
configuration is excluded; these results use the corrected, pinned configuration.

## Practical suitability

| Candidate | Cold-worker page median / p95, seconds | p95 / shipped | Peak process-tree RAM | Peak system RAM | Device-wide VRAM | Observed checks |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Shipped HOMR | 20.61 / 20.64 | 1.000x | 1.82 GiB | 71.9% | 1,569 MiB | Pass |
| Fine-tuned HOMR | 25.61 / 30.61 | 1.483x | 1.79 GiB | 67.7% | 1,572 MiB | Pass |
| Corrected 455 | 25.61 / 30.61 | 1.483x | 1.71 GiB | 70.9% | 1,569 MiB | Pass |
| Audiveris | 40.56 / 45.58 | 2.208x | 1.55 GiB | 76.9% | 0 MiB | Fail latency |
| Neutral Zeus | 70.58 / 71.19 | 3.449x | 1.07 GiB | 94.8% | 1,129 MiB | Fail latency and unattended screen |

All 59 page workers per candidate were cold. The field named `cold_start_seconds`
contains **complete cold-worker page elapsed time**, not isolated initialization
time; isolated startup overhead was not measured. Timings include failed pages.
Process-tree peaks and device-wide GPU readings are distinct measurements; the
GPU figures are not per-process allocation. Shipped used 75% system-RAM admission,
later runs 90%, and CPU execution profiles differ, so relative timings are
descriptive. The frozen eligibility limits remain 2x shipped p95, 75% of physical
RAM for the process tree, 90% VRAM and unattended operation. The newer 90% system
admission policy does not change the 75% process-memory rule.

All candidate sessions are closed and worker locks absent. Zeus had no inference
interruption but one scoring pressure interruption; it completed after RAM relief.
That attempt is pending/retried evidence, not a model failure or missing page.
Passing a bounded screen is not proof of deployment readiness. Zeus uses the
neutral CPU recognizer with its existing GPU detector; the separately defective
direct app extractor is outside these results.

## Promotion gates and candidate disposition

The frozen gate requires at least +0.03 primary F1 over verified fine-tuned HOMR
with statistical support, at most 0.01 pitch-F1 loss, at most 0.01 increases in
failure rate and penalized NED, no demonstrated conversion/stitching corruption,
and practical eligibility. Report against shipped HOMR as well; an inferior
fine-tune cannot displace it. The screen alone cannot satisfy promotion.

| Challenger versus fine-tune | +0.03 primary | Supported gain | Pitch loss <=0.01 | Failure increase <=0.01 | NED increase <=0.01 | Observed practical checks |
| --- | --- | --- | --- | --- | --- | --- |
| Corrected 455 | Fail | Fail | Fail | Fail | Fail | Pass |
| Audiveris | Fail | Fail | Fail | Fail | Fail | Fail |
| Neutral Zeus | Fail | Fail | Fail | Pass | Fail | Fail |

- **Shipped HOMR:** retain the installed control and fallback. Its descriptive
  lead and practical observations support retention, not a new promotion claim.
- **Fine-tuned HOMR:** retain as the verified approval baseline and an optional
  confirmation comparator. Its higher pitch F1 and zero failures are useful, but
  they do not override the lower primary estimate and unresolved paired uncertainty.
- **Corrected 455:** no larger accuracy-led confirmation now. Better conditional
  duration metrics do not offset its lower primary estimate and other failed gates.
- **Audiveris:** no larger confirmation of this configuration now; low accuracy,
  eight failures and latency failure give no replacement case.
- **Neutral Zeus:** no larger confirmation now; valid outputs coexist with very
  low primary accuracy and failed operating checks. A future controlled development
  diagnosis would need separate scope and must not tune on this screen.

HOMR 465/Combined require separately verified compatibility and development
admission. Current Qwen/Rokot complete-page configurations remain unready; LEGATO
and MuSViT remain unavailable. Unavailable entries are deferred, never scored zero.
Canonical Stage 5's bounded Qwen/Rokot follow-up needs a new request.

## Confirmation recommendation, exposure and runtime

**Recommend no accuracy-led challenger confirmation now.** If resolving shipped
versus fine-tuned uncertainty is a separate priority, preregister a paired future
evaluation before inference, with unchanged metrics/failures, whole compositions,
fixed identities/settings, multiplicity and explicit reuse/overlap disclosures.

The Stage 3 report's **343-page "untouched" wording is too strong**. The
[exposure audit](confirmation-exposure.json) verifies all 255 historical
report/sidecar hashes and inventories completed and partial inference by item ID,
without using prediction quality to derive the inventory:

| Inventory | Pages | Compositions |
| --- | ---: | ---: |
| Screen-disjoint remainder | 343 | 99 |
| Remainder with completed old shipped inference | 207 | 55 |
| Remainder without completed old shipped inference | 136 | 44 whole groups plus one page of an exposed group |
| Whole remainder groups without recorded prior inference attempt | 135 | 44 |

The partly processed Mozart KV576 group has four completed pages and a fifth
empty partial attempt, so it is excluded from the 44 whole-group inventory.
The other 48 historical completed pages overlap screening. Old Audiveris/Zeus
entry checks cover an already-exposed Bach page. The 44 groups comprise 24 Mozart,
18 Scarlatti, one Ravel and one Sousa composition, reflecting old processing order.
They are not a representative random holdout. Reference audits covered all 402
pages; no recorded candidate attempt does not prove no human review or training
overlap. This inventory is **not** a selected or frozen confirmation manifest.

| Candidate | 343-page extension hours / minimum sessions | 135-page inventory hours / minimum sessions |
| --- | ---: | ---: |
| Shipped HOMR | 5.09 / 2 | 2.00 / 1 |
| Fine-tuned HOMR | 5.98 / 2 | 2.35 / 1 |
| Corrected 455 | 5.92 / 2 | 2.33 / 1 |
| Audiveris | 5.03 / 2 | 1.98 / 1 |
| Neutral Zeus | 11.32 / 3 | 4.46 / 2 |

These scale observed same-PC complete-session time, including scoring, with a
four-hour cap and 30-second shutdown reserve. They exclude new admission/preflight,
extra retries and differing page complexity. Shipped plus fine-tuned would take
approximately **4.36 hours / at least two candidate sessions** on 135 pages, or
**11.07 hours / at least four candidate sessions** on the 343-page extension.
A stronger independent confirmation needs a separately eligible composition-
disjoint holdout with its population and review/training overlap audited. A
343-page run must be described as a screen-disjoint extension, not wholly untouched.

## Validation and handoff

- Fresh saved-evidence audit: 295 results, 295 scores, 1,257 declared artifacts,
  all five summaries/matrices and eight paired claims verified; no changed original.
- Exposure audit: 255 historical report/sidecar pairs verified, partial attempt
  preserved; immutable replay passed.
- Report/statistics/analysis fixtures: **14 passed**.
- Full research/bridge regression: **239 passed, 2 skipped, 9 subtests passed**;
  one expected unreadable-clef `music21` warning.

Exact commands, logs, the first audit's presentation-order check correction and
resumption boundary are in [job-record.md](job-record.md). The machine-readable
recommendation and evidence identities are in [decision.json](decision.json).
Stage 4 stops here. A later confirmation, Stage 5, training, cloud spend or
production change needs a separate user decision; none was started.
