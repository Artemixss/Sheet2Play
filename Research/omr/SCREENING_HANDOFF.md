# OMR screening execution handoff

**Status:** Historical screening Stages 1–4 complete, 2026-09-30.
**Archived plan:** [Screening comparison](../../plans/archive/2026-09-26-omr-screening-comparison.superseded.md).
**Historical successor:** [Zeus/shared repair plan](../../plans/archive/2026-10-03-zeus-attribution-repair.superseded.md),
now superseded; Phases 1–2 and bounded Phase 4 complete, Phase 3 qualified, Phase 5 deferred.
**Current plan:** [HOMR 465 and shipped-engine rhythm repairs](../../plans/MAIN_PLAN.md),
selected 2026-10-07; execution phases not started. Read the
[current handoff](reports/homr-timing-465/handoff.md) before a separately requested phase.
[Plans index](../../plans/README.md) records lifecycle status. Follow-up and
stop statements below describe their dated requests.

## Historical Zeus provenance follow-up — 2026-10-03

The user requested Phase 1 only of the [now-archived attribution/repair plan](../../plans/archive/2026-10-03-zeus-attribution-repair.superseded.md).
Read the separate [provenance ledger](reports/zeus-attribution/phase1/REPORT.md) and
[handoff](reports/zeus-attribution/phase1/handoff.md) for its acceptance status.
Historical screening outcomes/scores are preserved. This follow-up does not
authorize timing repair, rescoring, diagnostic inference, remedies, Rokot work or
any confirmation/promotion. The canonical Stage 4 decision below remains historical
evidence on the unchanged scoring identity.

## Canonical Stage 4 complete — evaluation and decision, 2026-09-30

The user requested Stage 4 using the completed five-candidate consolidated screen.
The [Stage 4 evaluation](reports/screening/v1/stage4-evaluation/REPORT.md) and
[machine-readable decision](reports/screening/v1/stage4-evaluation/decision.json)
close analysis for all five ready configurations. **Retain shipped HOMR; no
accuracy-led challenger confirmation now.** Fine-tune minus shipped remains
inconclusive (-0.0217, individual 95% CI [-0.0985, 0.0415]); no challenger has
supported superiority across eight Holm-adjusted claims. No promotion gate is met.

The [fresh evidence audit](reports/screening/v1/stage4-evaluation/screen-audit.json)
verified **295 results / 295 scores / 1,257 declared artifacts**, all summaries,
full duration matrices, source inputs and all paired statistics. It also reports
saved timeline-length/first-divergence diagnostics. Cold-start fields represent
complete cold-worker page time, not isolated initialization; training overlap is
unknown for all five. Audiveris/Zeus fail practical latency, and Zeus's resolved
scoring interruption limits unattended evidence. No new inference/scoring occurred.

The [exposure audit](reports/screening/v1/stage4-evaluation/confirmation-exposure.json)
qualifies earlier **343-page "untouched" wording**: the screen-disjoint remainder
contains **207 completed historical shipped outcomes**. Only **135 pages / 44 whole
compositions** have no recorded prior candidate attempt; the group inventory is
composer-biased and does not prove absence of review or training overlap. No future
sample was selected/frozen. Optional shipped/fine-tune evaluation would cost about
4.36 hours on that inventory or 11.07 hours on the partly exposed 343-page extension,
before fresh admission/preflight/extra retries.

Validation: **14 focused fixtures passed; full research/bridge regression 239 passed,
2 skipped, 9 subtests passed**, one expected music21 warning. All candidate sessions
closed, worker lock absent. Exact commands, logs, hashes and audit correction are
in the [Stage 4 job record](reports/screening/v1/stage4-evaluation/job-record.md).
Original reports, frozen contracts, helper code and shipped app remain preserved.

**Next decision:** the user may end comparison, request bounded Stage 5/readiness
work, or authorize a preregistered confirmation. Stop before that execution,
training, cloud spending or production promotion. The historical stage records
below remain evidence; their previous next-action notes are superseded here.

## Stage 3 complete — five-candidate consolidation, 2026-09-30

The user requested Stage 3 completion after the scoring-only pause. The
[consolidated report](reports/screening/v1/2c98d5638c36/reports/consolidated-stage3-836fb923bb33/REPORT.md) now verifies **295 result/score pairs**:
five candidates, each with the unchanged **59 pages / 18 complete compositions**.
Every result, score, declared artifact and source summary hash passed verification.
Historical controls were reused only after matching frozen sample/scoring contracts;
no inference or scoring was rerun for consolidation.

| Candidate | Primary F1 | Onset F1 | Pitch F1 | Failures | Penalized OMR-NED | Full session |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Shipped HOMR | 0.4061 | 0.4316 | 0.9701 | 1/59 | 0.3620 | 52.5 min |
| Repaired fine-tuned HOMR | 0.3844 | 0.4096 | 0.9841 | 0/59 | 0.3645 | 61.7 min |
| Corrected HOMR 455 | 0.2857 | 0.3060 | 0.9678 | 1/59 | 0.3851 | 61.1 min |
| Audiveris | 0.0986 | 0.1179 | 0.7568 | 8/59 | 0.5204 | 52.0 min |
| Neutral Zeus | 0.0228 | 0.0370 | 0.5763 | 0/59 | 0.8069 | 116.9 min |

Primary F1 is composition-macro pitch/onset/duration F1 with frozen failure
penalties. All 295 scores include OMR-NED; no scoring errors or missing scores.
The report retains full duration matrices, majority baselines, balanced accuracy,
macro-F1, missing/extra notes, feature coverage and failure categories.

Eight paired comparisons against shipped and repaired fine-tuned HOMR use
10,000 composition bootstrap samples, exact 262,144 paired assignments and
Holm correction. No challenger has supported superiority. Shipped HOMR leads
descriptively; fine-tuned minus shipped F1 is -0.0217, 95% CI [-0.0985, 0.0415].
The small difference is inconclusive with 18 compositions. Zeus minus shipped
is -0.3833, 95% CI [-0.5223, -0.2525]. These results do not diagnose whether its
accuracy loss comes from recognition, representation or conversion; valid output
on all pages is not evidence of accurate transcription. Training overlap remains unknown.

Audiveris and Zeus exceed the frozen 2x p95 latency limit (2.208x / 3.449x).
Zeus also has one historical scoring resource interruption at 94.8% system RAM;
it was resolved after the user freed RAM, with no model-failure penalty or omitted page.
Inference itself had no interruption. Sessions are closed and worker locks absent.
Historical control used 75% admission versus the later 90% policy and CPU profiles;
runtime comparisons remain descriptive. Provisional screen-disjoint 343-page totals
(the Stage 4 exposure audit above qualifies the original "untouched" wording),
including scoring, are 5.09 / 5.98 / 5.92 / 5.03 / 11.32 hours in table order;
these estimates do not authorize a confirmation run.

Report JSON SHA-256:
`22423ca7343b5382881577b6b6146066974cfd35710a48d964faa04b1ef8bb85`.
The [final consolidated audit](reports/screening/v1/stage3-cpu/consolidated-final-audit.json)
checks all five summaries, matrix support and derived duration metrics, and all eight
paired claims. Relevant report/statistics/analysis fixtures: **14 passed**.
Prior unchanged pipeline regression: **239 passed, 2 skipped, 9 subtests passed**.
Exact command, manifest, logs and closed parent are in the
[CPU job record](reports/screening/v1/stage3-cpu/job-record.md).

**Historical next action, completed by Stage 4 above:** review and decide using this consolidated evidence;
no accuracy-led challenger priority for confirmation is established by this sample.
Conditional HOMR 465/Combined and unavailable candidates remain deferred pending
separate compatibility/readiness work. Stop before untouched confirmation, Stage 5,
training, cloud spending or production promotion. The earlier HOMR-only Stage 4
analysis remains complete within its original scope; this closeout completes Stage 3.

> **Historical Zeus scoring-only pass complete (consolidation later authorized), 2026-09-30:** User freed RAM; preflight69.5%/4.65GiB.
> The unchanged scorer reused23 verified scores, retried page24 and exited0 without further
> interruption. All59/59 results and exact CPU score identities/hashes passed the final
> audit; immutable59-page/18-group summary SHA-256 `bea1ff52d402e4a8adb3dda97c4c4cfbd696bdd24db2fcacb9bd2f11979272ef`.
> Session closed at7011.924seconds (116.9minutes) cumulative. All59/324systems/1061
> preserved raw files remain verified. Stop now before consolidation; a later stronger-model
> pass completes cross-candidate analysis and Stage3.

> **Historical assistant-model pause, 2026-09-30 (scoring later resumed):** Zeus inference is complete:
> **59/59 successful outcomes**, verified result/artifact hashes plus324 systems and1061
> preserved raw-file hashes. Inference took **64.8 minutes**, no interruptions,
> RAMpeak69.7%, deviceVRAM1129MiB. Fresh development/admission passed;46 relevant
> fixtures and full regression **239 passed,2 skipped,9 subtests** passed.
> **23/59 scores** passed exact CPU identity/hash checks; all23 OMR-NED scores valid.
> Page24 (`test/beethoven/sonata26_1/sonata26_1_1.png`) remains **pending**, after
> sustained90% RAM pressure (peak94.8%, resource interruption, not a model failure).
> Scorer parent77506 exited1 before the user's pause; no worker/lock remains.
> Cumulative session is closed at **5432.674 s (90.5 min)**; do not reset its budget.
> The [pause audit](reports/screening/v1/stage3-cpu/zeus-pause-audit-20260930.json)
> and [CPU job record](reports/screening/v1/stage3-cpu/job-record.md) preserve the resume point.
> **Historical next action at the earlier pause:** free RAM and recheck resources/identities;
> run the unchanged scorer with `--retry-pending` under the same session, reusing23
> verified scores. The cheaper-model pass should stop after all59 scores/summary
> verify; leave five-candidate consolidation/final review for the later stronger-model
> request. Stage3 remains incomplete. No automatic restart, confirmation, Stage5,
> training or promotion.

> **Historical stop before Zeus, 2026-09-29 (superseded above):** Audiveris is complete;
> Zeus and Stage 3 consolidation remain for a later prompt. [CPU job record](reports/screening/v1/stage3-cpu/job-record.md)
> saves the runtime-access investigation, exact commands, source/configuration hashes,
> logs and resume state. The [new v5 CPU manifest](reports/screening/v1/manifest-v5-607ff64134da.json)
> pins the fully readable runtime inventory; the 59-page sample, frozen scoring and
> 90% resource policy are unchanged. Old freezes and HOMR results remain preserved.
> Audiveris development/admission passed (25.6 s, RAM 72.7%, eight CPU affinity/thread
> limits, no VRAM); final regression **239 passed, 2 skipped, 9 subtests passed**.
> Audiveris inference completed and verified **59/59 outcomes: 51 successes, 8 failures**,
> 36.8 minutes, peak RAM 76.9%, no interruption. Parent 54939 closed successfully.
> All **59 scores** and the immutable summary verified; scoring parent 26551 exited
> zero. Full session **52.0 minutes**, no inference/scoring interruption, no live
> candidate or worker lock. Primary F1 **0.0986**; five recognition and three invalid
> output failures. Zeus development/admission/inference/scoring have not started.
> **Historical next action:** wait for the later Zeus request; run its recorded fresh complete-page
> development/admission, 59-page screen and score, then publish the five-candidate report.
> Stage 3 remains incomplete. Stop before confirmation, Stage 5, training or promotion.

## Historical Stage 3 stop — Audiveris complete, 2026-09-29

The native CPU Audiveris configuration `3f340c6bab3e` completed the unchanged
59-page/18-composition sample under the pinned readable v5 runtime and 90% policy.
No recognition parameters, source, weights, references or scoring rules were tuned
from these predictions. The [inference audit](reports/screening/v1/stage3-cpu/audiveris-inference-audit.json)
and [final audit](reports/screening/v1/stage3-cpu/audiveris-final-audit.json) verify
every result identity/artifact inventory, every exact CPU scorer identity/hash,
and the [immutable summary](reports/screening/v1/2c98d5638c36/summaries/audiveris_page/3f340c6bab3e/summary-2904e7a12f86.json).
Summary SHA-256: `a9724dee8137993ff1c2133b351bc65df5157c10d8db1e1e6af151763cd0d1a8`.

| Candidate | Primary F1 | Onset F1 | Pitch F1 | Failures | Penalized OMR-NED | Full session |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Audiveris | 0.0986 | 0.1179 | 0.7568 | 8/59 | 0.5204 | 52.0 min |

All 51 successful outputs have valid OMR-NED scores, and all eight failures retain
penalty 1.0; no scoring errors or omissions. Five failures are
`AUDIVERIS_FAILED:recognition`, three `AUDIVERIS_OUTPUT_INVALID:artifact_capture`.
The result is descriptively below shipped HOMR's primary F1 0.4061; the consolidated
paired statistics and eight-claim Holm correction are pending Zeus, so no new
statistical conclusion is claimed here. No shifted/aligned scoring or benchmark repair.

Duration balanced accuracy **0.3880**, macro-F1 **0.3521**, majority accuracy
**0.4224**, majority macro-F1 **0.0238**; predictor is not single-class.
The full sparse matrix (67 nonzero cells, 25 labels) sums to all 2,185 matched
pitch/onset notes; unmatched expected/predicted notes 16,863/16,708 remain outside
these conditional duration diagnostics and inside headline penalties.
Missing/extra transcription notes: 20,159/17,089. Training overlap remains unknown.

Inference took 36.8 minutes; scoring and summary overhead took 15.1 minutes.
All 59 workers were cold starts; page latency median/p95 **40.56/45.58 seconds**.
System RAM peak **76.9%** (scoring 72.3%), device-wide VRAM **0 MiB**;
59 inference and 59 score attempts, no interruptions, closed session `stage3-audiveris-screen-01`.
Observed process-memory, VRAM and bounded unattended checks passed; latency failed
the frozen p95 limit (**2.208×** shipped versus maximum 2×). Historical control
timings used 75% admission and a different execution context, so timing comparisons
remain descriptive. These observations do not establish deployment eligibility.

The five-candidate consolidation implementation and eight fixtures are prepared;
full research/bridge regression **239 passed, 2 skipped, 9 subtests passed**.
No consolidated report was published with Zeus missing. All 177 prior HOMR results
and scores were independently reverified without regeneration. The exact Zeus
development command is recorded at the end of the CPU job record; no fresh Zeus
admission exists under this v5 manifest. Later work must reverify runtime/source/input
identity before admission and retain the CPU recognizer with its existing detector.

> **HOMR-only Stage 4 complete, 2026-09-28:** Both repaired candidates passed fresh
> complete-page development and 90% admission under the [combined v4 manifest](reports/screening/v1/manifest-v4-e31f2e628e16.json).
> Each completed all 59 outcomes and scores; every identity, artifact and summary hash
> verified against the unchanged frozen sample/scorer. The [final HOMR-only report](reports/screening/v1/2c98d5638c36/reports/homr-only-stage4-e35f73ca9f75/REPORT.md)
> gives primary F1 **0.4061 shipped / 0.3844 fine-tuned / 0.2857 corrected 455**.
> No challenger has a supported gain over shipped HOMR. Keep the installed engine.
> No worker or lock remains. [The job record](reports/screening/v1/stage4-homr/job-record.md)
> preserves exact commands, identities, logs, progress and final evidence.
> **Historical stop:** superseded by the Stage 3 authorization above.
> Confirmation, training and promotion remain unauthorized.

## Stage 4 — corrected HOMR-only analysis (complete within requested scope)

The user authorized corrected fine-tune/455 prerequisites and analysis after the earlier
RAM-work pause. The same **59 pages / 18 complete compositions** were retained; shipped
HOMR was verified under its original v1 manifest without repeating inference/scoring.
The incompatible historical 455 configuration `cb45056ebb22` is excluded from ranking.
No learned weights, frozen scoring rules, or production assets changed.

| Candidate | Primary F1 | Onset F1 | Pitch F1 | Failed pages | Penalized OMR-NED | Inference + scoring |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Shipped HOMR | 0.4061 | 0.4316 | 0.9701 | 1/59 | 0.3620 | 52.5 min (historical) |
| Verified fine-tuned HOMR | 0.3844 | 0.4096 | 0.9841 | 0/59 | 0.3645 | 61.7 min |
| Corrected HOMR 455 | 0.2857 | 0.3060 | 0.9678 | 1/59 | 0.3851 | 61.1 min |

- Fine-tune minus shipped primary F1: **−0.0217**, 95% composition bootstrap interval
  **[−0.0985, 0.0415]**. Corrected 455 minus shipped: **−0.1204**, interval
  **[−0.2536, 0.0199]**; corrected 455 minus fine-tune: **−0.0988**, interval
  **[−0.2375, 0.0462]**. All intervals cross zero. All four reported one-sided
  superiority claims have Holm-adjusted p **1.0**. This limited screen provides
  no supported gain and does not establish a definitive full-dataset ordering.
- Intervals use 10,000 composition resamples; superiority uses all 2^18 paired
  composition label swaps under the exchangeable-label null. The historical
  bootstrap-tail fraction was not a null-test p-value and is not reused.
- Duration balanced accuracy / macro-F1 / majority baseline accuracy: shipped
  **0.5775 / 0.5218 / 0.4741**, fine-tune **0.6143 / 0.5480 / 0.4279**, corrected
  455 **0.6228 / 0.5688 / 0.3989**. All are nondegenerate. These diagnostics condition
  on matched pitch/onset notes; unmatched notes and failures remain in headline
  transcription scoring. Higher conditional duration scores do not establish better
  end-to-end timing. Full sparse confusion matrices, class labels/support and baseline
  macro-F1 are in [report JSON](reports/screening/v1/2c98d5638c36/reports/homr-only-stage4-e35f73ca9f75/report.json).
- Fine-tune had no failed page; corrected 455's `test/joplin/breeze/breeze_2.png`
  produced no MusicXML (`HOMR_OUTPUT_MISSING`, conversion). All 59 scores include
  frozen penalties, with **zero OMR-NED scoring errors**. No page was dropped or retried.
- Both new candidates had exactly 59 inference and 59 scoring attempts, no resource
  interruption, and closed sessions well below four hours. Fine-tune peak sampled
  system RAM **67.7%**, device-wide VRAM **1,572 MiB**; corrected 455 **70.9%** RAM
  including scoring (69.5% inference), **1,569 MiB** VRAM. Median/p95 page latency:
  fine-tune **25.61/30.61 s**, corrected 455 **25.61/30.61 s**, shipped **20.61/20.64 s**.
  All observed frozen practical-limit checks pass; the historical 75% control and
  current 90% admission policies make timing comparisons descriptive. The separate
  frozen 75% process-tree RAM eligibility rule is unchanged.
- Training overlap for fine-tune/455 and cross-staff coverage remain unknown.
  Available density, document length, voice, tie, tuplet, meter and repeat breakdowns
  are reported descriptively. No tuning followed screening observations.

**Decision:** retain shipped HOMR. Neither challenger has accuracy-led confirmation
priority from this screen. Corrected 455 also fails all numerical screen checks against
the fine-tune (+0.03 primary gain/support, pitch loss, failure and penalized-NED limits).
This does not prove every conversion/stitching path is sound or satisfy promotion.
For a separately authorized untouched 343-page remainder, observed throughput estimates
are **5.1 h shipped / 6.0 h fine-tuned / 5.9 h corrected 455**, at least two bounded
sessions per candidate. These are estimates, not jobs launched.

Validation: **219 passed, 2 skipped, 9 subtests passed**, expected music21 fixture
warning only; [regression log](reports/screening/v1/stage4-homr/analysis-regression.log).
Final report JSON SHA-256: `d2a8d0a48bc3eb7cc929f8969ae38449b58565ef98f32fc22b8b892c63a0e5eb`.
The [final verification record](reports/screening/v1/stage4-homr/final-verification.json)
confirms unchanged source/manifest hashes, 177 verified results/scores, closed sessions
and absent lock. Documentation links and `git diff --check` passed.
The [job record](reports/screening/v1/stage4-homr/job-record.md) contains admissions,
manifest/configuration hashes, inference audits and summary identities. No app publish
was needed for research-only changes. Stop before any later stage; in a new request,
preflight/admit/screen/score Audiveris and Zeus sequentially, then consolidate before
deciding whether any untouched confirmation is justified.

> **Historical fine-tune intake, 2026-09-28 (stop superseded by Stage 4 above):** The user requested Phases 1–3 of the
> [fine-tune export repair plan](../../plans/archive/2026-09-28-homr-finetune-export-repair.done.md), stopping before
> Phase 4 screening. **Phases 1–3 are complete.** Private report commit `9bf0d47`
> supplies verified source/tokenizers, strict checkpoint loads and CPU ONNX parity.
> New provenance binds the existing binaries; the historical decoder hash remains stale.
> The [final v4 child manifest](reports/screening/v1/manifest-v4-502777eed80a.json) pins
> the isolated source/runtime, model files, shared helpers and disabled tuplet override.
> All three fixed development pages passed on local CUDA with complete MusicXML and
> canonical-event artifacts. [Fresh admission](reports/screening/v1/2c98d5638c36/admissions/fine_tuned_homr/9fa13d27f0b7/admission-23d1108e5364.json)
> and [local verification](reports/screening/finetune-export/local-entry-verification.json)
> recheck their hashes, loaded models, providers and unchanged 59-page/18-composition sample.
> Regression: **213 passed, 2 skipped, 9 subtests passed**. The remote CUDA error 9
> did not reproduce locally; its failure log remains preserved. No training, re-export,
> new binary transfer, production change, or frozen fine-tune screening occurred.
> **Stop before Phase 4; a new request is required.** See the
> [job record](reports/screening/finetune-export/job-record.md) for commands and identities.
> The chat retrieval failure did not prove that the remote PC was offline.

> **HOMR 455 correction, 2026-09-27:** The complete 455 release source is now pinned
> at `a4865663e7278f908d6d1b1a57d549f9ca3d1067`. A checked-in vocabulary/ONNX
> contract and fail-closed validator produce the [new v3 manifest](reports/screening/v1/manifest-v3-0b5eb110e968.json)
> and [compatibility report](reports/screening/v1/compatibility/homr455-3c9f495122d6.json).
> Three complete-page development runs passed under the final identity, and a new
> [admission](reports/screening/v1/2c98d5638c36/admissions/homr_455/a2411bef278d/admission-4252a5d236bd.json)
> was issued. The [correction job record](reports/screening/v1/stage3-homr455-correction-job.md)
> has commands, hashes, logs, outcomes and the stop state. **No corrected 59-page screen
> or score was run.** The v2 results below remain invalid for 455 model-quality ranking.
> This correction's development-only RAM limit was 95%, explicitly authorized by the
> user; the saved v3 runner policy is still 75%. The separately selected 90% policy for
> future screening needs its own versioned runner and manifest before inference.

> **Resource-policy update, 2026-09-27:** The [active comparison plan](../../plans/archive/2026-09-26-omr-screening-comparison.superseded.md)
> now sets a 90% system-RAM admission and sustained-pressure threshold for future
> screening runs. The 75% figures below describe completed runs and their frozen
> manifest identities. The [v4 manifest](reports/screening/v1/manifest-v4-3af78028afa2.json)
> records the new policy, and new preflight/development/screening/scoring work now
> uses 90%. Old manifests remain readable as evidence but are rejected for new
> candidate work. Re-admit each candidate on v4 before inference; none was run as
> part of this policy change. Preserve the separate frozen Phase-1 eligibility rule.

> **Review finding, 2026-09-26:** [Interim HOMR review](SCREENING_HOMR_REVIEW.md)
> identifies an incompatible 455 model/source pairing: its decoder has three position
> classes, while the screened source has five and maps class 2 to `upper2` instead of
> the 455 release's `lower`. Preserve the results below as historical evidence, but
> do not use the 455 comparison to rank correctly configured models. Corrected intake,
> development validation and a new configuration identity are recommended before a rerun.
> The review performed no inference, runtime edits or training.

**Historical Stage 1–2 closeout:** Created 2026-09-26 after the user selected the [canonical screening plan](../../plans/archive/2026-09-26-omr-screening-comparison.superseded.md). **Stages 1 and 2 are complete; the requested HOMR-only part of Stage 3 is complete.** No training, model swap, or confirmation evaluation has started. Audiveris and Zeus remain for another request.

## Stage 3 — HOMR-only screen, 2026-09-26 (complete within requested scope)

- Shipped HOMR passed exact-pipeline development admission and completed 59/59 screening outcomes (58 successes, one typed `HOMR_OUTPUT_MISSING`) and 59/59 verified item scores. Composition-macro pitch/onset/duration F1: **0.4061**; onset F1 **0.4316**; pitch F1 **0.9701**; failure rate **1/59**. The immutable summary is [here](reports/screening/v1/2c98d5638c36/summaries/homr_page/0a0004e3c354/summary-a05240e60206.json). Its inference/scoring session used 3,150.049 seconds, below the four-hour cap. Two transient Windows atomic-publication denials were recovered from hash-verified staged results without repeating candidate inference or scoring.
- Fine-tuned HOMR remains blocked: the local decoder hash `54c4940a2c8f8ca2c340744f29ea6a90a1645973ee7195d127d1b2c776609fce` conflicts with export-manifest hash `daee4ce3029e53af46bd3f3ea08528ed2af3e5770cb3e75f4fc67926bdd5c685`, and the source checkpoint is unavailable locally. No unverified export was run.
- HOMR 455 has an isolated pinned source/runtime/model identity in [manifest v2](reports/screening/v1/manifest-v2-0de561e2ae9d.json), preserving the original 59-page sample and shipped control. Its exact-pipeline complete-page development result and [admission](reports/screening/v1/2c98d5638c36/admissions/homr_455/cb45056ebb22/admission-dd8e6d691762.json) passed. All **59/59** screening outcomes and artifacts verify: 58 successes and one typed `HOMR_OUTPUT_MISSING` conversion failure at `test/joplin/breeze/breeze_2.png`; no pending attempt. All 59 scores and their [summary](reports/screening/v1/2c98d5638c36/summaries/homr_455/cb45056ebb22/summary-4bdaa581f5f2.json) verify. Inference used 1,345.172 seconds; the full inference/scoring [session](reports/screening/v1/2c98d5638c36/sessions/homr455-screen-01.json) closed at 3,938.625 seconds, below four hours. Sampled system RAM peaked at 77.8% without sustained 30-second pressure; device-wide VRAM peaked at 1,571 MiB. No candidate/scorer worker or lock remains.
- The verified [interim HOMR report](reports/screening/v1/2c98d5638c36/reports/interim-homr-dd1c0a4aeea5/REPORT.md) compares 59 pages across 18 complete compositions. Shipped HOMR vs HOMR 455: composition-macro pitch/onset/duration F1 **0.4061 vs 0.2819**; onset F1 **0.4316 vs 0.3045**; pitch F1 **0.9701 vs 0.9622**; failure rate **1/59 each**; failure-penalized OMR-NED **0.3620 vs 0.6628**. Paired 455-minus-shipped primary F1 is **−0.1242**, 95% composition bootstrap interval **[−0.2557, 0.0155]**, Holm-adjusted one-sided superiority p **0.9608**. The interval includes zero; this bounded screen does not establish a significant advantage or authorize promotion. Duration balanced accuracy **0.5775 vs 0.4392** and macro-F1 **0.5218 vs 0.3793**; neither duration classifier is single-class. Full confusion matrices, latency, resources, failure details, and missing-candidate statuses are in [report JSON](reports/screening/v1/2c98d5638c36/reports/interim-homr-dd1c0a4aeea5/report.json). The fine-tuned-HOMR baseline was unavailable, so the plan's paired comparison against it cannot yet be reported.
- The detailed commands, identities, logs, and interruption handling are in the [Stage-3 job record](reports/screening/v1/stage3-homr-job.md). Focused representation/conversion fixtures passed (5 tests), and the full research/bridge regression passed: **184 passed, 2 skipped, 9 subtests passed**. Research-only changes did not require publishing the desktop app. **Exact next action:** Stop this request. In a separate Stage-3 request, preflight and admit Audiveris and Zeus under their frozen identities, screen and score one at a time, then create the consolidated report after both are complete. Reconcile the fine-tune export decoder/provenance separately before attempting its inference. Do not start the old 20-stage sequence, training, confirmation evaluation, or promotion.

## Stage 2 — frozen sample and tooling, 2026-09-26

**Boundary:** Stage 2 selected and froze the screen and implemented gated prepare, development admission, run, score, and report commands. No candidate screening page was inferred, scored, or reported. The old 20-stage sequence remains retired. Working directory: `C:\Users\bur4x\Desktop\lecture\big_projects\Sheet2Play`.

### Frozen sample

- Active [manifest](reports/screening/v1/manifest-v1-9126bc5feefc.json): **18 entire composition groups, 59 pages** from frozen 402-page SMB pianoform. Remaining collection: 99 groups/343 pages, with zero group overlap. Manifest file SHA-256 `1cf36e06b12a0ce72f7bb1e8e358ea9a8b374449f807f11e4a843f351158e1ee`; canonical payload identity `9126bc5feefc1cf919831716f045cc00b1b71347c02503f10c3a86d1ca2c6c7c`; stable sample identity `2c98d5638c368b1a53bdb3440177d04fa585f9b1ca6ce6adbe65af64cd8e27d1`.
- Selection is deterministic: for each page-count stratum, sort by SHA-256 of UTF-8 `20260926` directly concatenated with the composition ID (composition ID breaks any digest tie), take seven groups with 1–2 pages, eight with 3–4, and three with at least five; include every page of each chosen group in frozen manifest order. This uses only frozen manifest metadata. The selected group IDs, item IDs, image/source region/reference hashes, protocol/scorer hashes, and exact algorithm are in the manifest. An early preparation draft is preserved under `reports/screening/v1/superseded/`; it has no results and fails current identity verification.
- Metadata coverage: independent voices 45/59 pages, ties 59/59, tuplets 19/59, repeats 24/59, meter changes 1/59; note-token count 53–442. Cross-staff is **unknown on all 59**. Inspection found no cross-staff field in any of the 402 frozen primary pages or the 20 open/12 controlled development entries, and no named cross-staff development fixture. That is a metadata/fixture gap, not proof that cross-staff notation is absent. No benchmark page was added by hand; investigate the feature on development fixtures before making a cross-staff accuracy claim.
- The pinned Phase-1 protocol is SHA-256 `0fdc0796ee68aa6920f2be20cab98e73b7565682a987eb9bedea6b2f210f809b`; scoring implementation SHA-256 `b5f4b33484454e7e0e1affb008a0ae47d791af127f283cc76ac09b8da31c2e97`. The historical Phase-3 freeze remains SHA-256 `3fdd3d76aeab4188244795ea7b5eb310b2129d8d50131290297aeb1a32020633` and is not repurposed as the screening manifest.

### Candidate identities and gates

| Candidate | Screening identity SHA-256 | Stage-2 status |
| --- | --- | --- |
| Shipped HOMR `homr_page` | `0a0004e3c354793271a4298ec7a8c14ff68653acd1704d2cf9e0ffa30250ce51` | Requires a complete-page development smoke with this exact screening pipeline before Stage-3 inference. Stage-1 smokes used a different supervisor identity. |
| Audiveris `audiveris_page` | `0f78f31f437954c358b50adaa8996031d2b80bd013268c2f2fb37238b02e3063` | Same exact-pipeline development gate; native CPU route. |
| Zeus `zeus_page` | `deb07fa750b57273044730c7472a42cfc3a46b8b4f9c239ffa64108997f613dd` | Same exact-pipeline development gate; corrected neutral CPU route. |
| Fine-tuned HOMR | None | Export manifest decoder hash still differs from local decoder; source checkpoint/decoder identity needs reconciliation. |
| HOMR 455 | None | Isolated runtime, source, exact weights, decoder/tokenizer, and precision have not been verified here. |

The runnable entries pin current adapter configuration, source/normalizer files, runtime/weights, and the eight-thread, below-normal resource policy. A later verified configuration creates a new immutable identity while the sample identity stays fixed. No historical predictions were imported: the limited-resource HOMR pipeline differs from the old Phase-3 configuration. Existing screening results can be skipped only after their identity, typed status, and every declared artifact hash pass; interrupted attempts remain pending. Historical timings will not enter screening latency summaries.

### Tooling and use after a Stage-3 request

- `screening_prepare.py` writes/rechecks the immutable manifest. `screening_admit.py` checks a successful complete-page development result, its immutable sidecar, input image, resource-policy witness, and artifact hashes. This admission is not yet present for any candidate.
- `screening_run.py` refuses to launch without matching admission, enforces one worker through a PID/creation-time lock, at most five pages per chunk, cumulative four-hour session time across restarts, below-normal priority/eight-processor affinity and supported thread caps, five-second system RAM/device-wide VRAM samples, and the 75%/90% pressure policy with a 30-second stop window. A worker's frozen timeout is a typed completed failure; resource/session/runtime interruption is pending. Raw attempts and console logs remain separate from atomic result-plus-identity directory commits. A staged result is hash-verified and promoted on checked resume without duplicate inference; partial retries require an explicit flag.
- `screening_score.py` requires all **59** verified completed outcomes before scoring. It calls the unchanged Phase-1 `score_result`, commits per-item scores with immutable identities, applies failure penalties, and uses the existing Phase-3 summary logic. It uses the same lock/session budget, so it cannot score alongside inference. Session-complete timings are kept distinct from recovered adapter-only timing. `screening_report.py` requires complete score sets, keeps missing candidates visible, reports the full duration/failure/resource diagnostics, and computes composition-grouped paired intervals with Holm adjustment. An 18-composition screen cannot authorize production promotion.

Command interfaces (the development report and admission paths must first be generated and verified during Stage 3):

```powershell
$screeningManifest = 'Research/omr/reports/screening/v1/manifest-v1-9126bc5feefc.json'
Research/omr/.venv/Scripts/python.exe Research/omr/screening_prepare.py
Research/omr/.venv/Scripts/python.exe Research/omr/screening_admit.py --manifest $screeningManifest --candidate homr_page --development-report $developmentReport
Research/omr/.venv/Scripts/python.exe Research/omr/screening_run.py --manifest $screeningManifest --candidate homr_page --admission $verifiedAdmission --session-id homr-screen-01 --start-index 1 --max-items 5
Research/omr/.venv/Scripts/python.exe Research/omr/screening_score.py --manifest $screeningManifest --candidate homr_page --session-id homr-screen-01
Research/omr/.venv/Scripts/python.exe Research/omr/screening_report.py --manifest $screeningManifest --kind interim-homr --candidates homr_page
```

`$developmentReport` and `$verifiedAdmission` are deliberately unset until real Stage-3 evidence exists. Run and score commands are **not** instructions to execute them under Stage 2.

### Validation and stop state

- [Gate checks](reports/screening/v1/stage2-validation/gates.json): repeated prepare returned the same manifest; run rejected missing development admission; score rejected missing result at item 1/59; report rejected missing scores. No candidate process started.
- [Focused Stage-2 tests](tests/test_screening_stage2.py) cover deterministic selection/group integrity, disjoint remainder, immutable completed successes/failures, hash corruption, staged recovery, pending interruptions, duplicate-worker lock recovery, cumulative session cap, five-page bound, frozen scorer agreement on failure and identical-note fixtures, development admission checks, and paired/bootstrap report math. Full research + bridge regression: **179 passed, 2 skipped, 9 subtests passed** with one expected music21 warning; log: [regression.log](reports/screening/v1/stage2-validation/regression.log).
- [Final check](reports/screening/v1/stage2-validation/final-check.json): all **255** original report/sidecar pairs, **1,008** artifact hashes, and **47** preserved old state/log files still match Stage 1. Screening attempts/completed results/scores are **0/0/0**; no worker or lock remains. Frozen Phase-1, original Phase-3, and historical reports were not modified. Research-only changes did not require publishing the desktop app.

**Exact next action:** Stop. On an explicit Stage-3 request, inspect live processes/resources again, then validate the shipped HOMR screening pipeline on a real complete development page under its pinned identity and resource limits; create its admission record, run at most one five-page chunk, and continue only within the selected Stage-3 scope. Resolve the fine-tune decoder/export mismatch and pin an isolated 455 configuration before admitting either. Do not start the old sequence, training, or a larger confirmation run.

## Stage 1 execution record — 2026-09-26

Working directory for every command: `C:\Users\bur4x\Desktop\lecture\big_projects\Sheet2Play`.
Evidence directory: `Research/omr/reports/screening/stage1-20260926/`.

- Read-only process inventory found no sequence, completion monitor, Python candidate, Java/Audiveris, or llama worker. Old PIDs 24440, 26892, and 3292 are absent. `processes-before.json` preserves executable, command line, PID, parent PID, and creation time for matching processes; the unrelated WSL service has inaccessible executable/command fields.
- `screening_stage1_audit.py --output Research/omr/reports/screening/stage1-20260926/recovery-v2` verified the exact historical freeze and both audits: 402/402 primary and 611/611 secondary. All 255 report/sidecar pairs pass, including 251 successes and four `HOMR_OUTPUT_MISSING` failures (items 18, 82, 117, 185). All 1,008 declared artifacts match hashes and byte counts. No corrupt or unexpected reports. A first attempt stopped after freeze verification because the new auditor omitted the required collection argument; fixed before the v2 run. Historical evidence was not modified.
- Item 256 is `test/mozart/Sonate_in_D_-_KV_576/153.png`; its raw directory `53dafd18de30dbbb085a-ebf2773246e5-635ffae17143` is empty, with no report/sidecar. It and the other 146 uncompleted pages remain pending, not failures. `recovery-v2/preserved/` contains verified copies of 47 old state/log files plus the empty partial directory. Original stale state is preserved; the separate recovery record reconciles it as `interrupted_retired_do_not_resume`.
- Recovery eligibility is conditional on the exact historical identity. Resource-limited development uses a new configuration identity; do not automatically reuse old predictions for that identity or pool old and new latency measurements.
- PC: Ryzen 7 7735HS, 8 cores/16 logical processors, 15.25 GiB usable RAM, RTX 4050 Laptop GPU with 6,141 MiB device memory, driver 591.86. Initial C: free space 57.95 GiB. Initial 30-second baseline was 81.8–82.2% RAM and 0 MiB device-wide VRAM, so no worker was admitted. Later `preflight-v1.json` measured 70.7–72.0% RAM for 30 seconds and passed admission observation.
- System/Application events (12:00–14:30 local), Resource-Exhaustion operational events (12:00–13:30), and crash/resource metadata are saved in the evidence directory. Kernel-Power 41 at 13:06:36 records an unclean reboot, bugcheck code 0, WHEA boot-error count 0. Event 6008 reports previous shutdown 12:48:17, which conflicts with the last report mtime 12:52:26; do not infer an exact crash time from that field. No recorded WHEA/display-driver/resource-exhaustion fault was found in that window. The resource detector log contains only its post-boot start. No current crash dump or PerfLogs trace was found; the only minidump is dated August 11. Opera pressure is plausible but not a demonstrated cause.
- Shipped HOMR, Audiveris, Zeus runtime/source/model inventories match the old freeze. The three planned development first-page images and whole-composition MusicXML references pass frozen hashes. Fine-tune export remains unverified: local decoder SHA-256 `54c4940a2c8f8ca2c340744f29ea6a90a1645973ee7195d127d1b2c776609fce` differs from manifest `daee4ce3029e53af46bd3f3ea08528ed2af3e5770cb3e75f4fc67926bdd5c685`. No fine-tune run, source change, download, or training was performed.

### Development resource preflight job (recorded before launch)

Command:

```powershell
Research/omr/.venv/Scripts/python.exe Research/omr/screening_stage1_development.py --output Research/omr/reports/screening/stage1-20260926/development-v1
```

- Three pages, sequentially: `openscore-6211535-page-1`, `openscore-6211549-page-1`, `openscore-6211555-page-1`, selected by existing development-manifest order without benchmark predictions. Input/reference hashes are in `preflight-v1.json`; references cover compositions and are not used as page-level scoring truth.
- Shipped HOMR only, with an isolated research launcher. Eight-thread CPU cap, eight-processor affinity, ONNX intra-op 8/inter-op 1/sequential execution, OpenCV and BLAS/OpenMP cap 8; below-normal priority at worker/engine creation. The installed ONNX runtime has no PyTorch or psutil; the engine launcher uses Windows APIs for priority/affinity and does not install packages. Shared adapter and shipped launcher are unchanged.
- Five-second system-RAM/device-VRAM/CPU/disk samples; persistent stdout/stderr; 75% RAM/90% VRAM admission gate; continuous pressure for 30 seconds stops the process tree and retains a pending partial attempt. Original 600-second HOMR timeout remains a typed failure. Three pages are below the five-page chunk maximum; session deadline is four hours with a 30-second shutdown reserve. No concurrent scoring.
- Logs: `development-v1.log`; per-page process identity, configuration identity, raw artifacts, resource samples, and outcomes under `development-v1/page-N/`. Exclusive lock `.runtime/screening-stage1-development.lock`; inspect its PID/creation time and outputs before any retry. Do not remove a live lock or launch a second worker.
- Contract/recovery/resource fixtures before launch: **55 passed** (`focused-tests-v2.log`).

### Completed development runs and validation

The development supervisor started at **14:06:45 Europe/Istanbul**, PID **9660**, creation epoch `1790420805.1726544`; all three pages finished by **14:07:42**. The run stopped normally, removed its lock, and left no candidate worker. Each `page-N/process.json` records the child executable, command, PID, and creation time. After a user-reported usage interruption, the **17:18:51** resume check again found no candidate worker or lock; nothing was relaunched.

All three produced native tokens, MusicXML, nonempty canonical events, and engine logs, with no normalization warnings. All **12 declared development artifacts** passed SHA-256 checks. These are functional development results, not recognition-accuracy scores. Their shared configuration hash is `8c5df6ade390ed7791686dfa1eb2c82ea0790c4efa7ce4e61211c3eb23a329a3`; it includes the resource-limited launcher/supervisor hashes and differs from the historical HOMR configuration.

| Development page | End-to-end elapsed | Engine process-tree peak RAM | System RAM peak | Device-wide VRAM peak | Canonical notes |
| --- | ---: | ---: | ---: | ---: | ---: |
| `openscore-6211535-page-1` | 20.59 s | 1.44 GiB | 80.5% | 1,413 MiB | 222 |
| `openscore-6211549-page-1` | 15.64 s | 1.50 GiB | 78.2% | 1,165 MiB | 181 |
| `openscore-6211555-page-1` | 15.61 s | 1.74 GiB | 81.9% | 1,567 MiB | 43 |

End-to-end times cover cold worker startup, input verification/copy, segmentation, recognition, native conversion, shared normalization, report writing, and detection of completion on the five-second monitor interval. Recognition/conversion times were 14.63/9.55/11.77 seconds; normalization took 0.67/0.59/0.54 seconds. Process-tree RAM uses 0.2-second samples; system RAM, CPU and device-wide VRAM use five-second samples, so these are observed peaks, not guaranteed instantaneous maxima. Peak sampled system CPU was 44.7%; minimum C: free space was 57.99 GiB. Device readings are not per-process VRAM.

Each page was admitted below 75% RAM. In-run RAM crossed that threshold briefly, but no interval persisted for 30 seconds; no resource termination occurred. This demonstrates short development operation, **not sustained unattended stability**. Reduce background RAM use before a longer session and retain the prescribed admission/stop policy. No parameter was chosen from frozen predictions. Audiveris and Zeus identities were reverified, but their new limited-resource smokes belong to candidate admission later; these three new runs used shipped HOMR only. HOMR 455 has no locally verified isolated candidate identity in this preflight and must be provisioned/pinned before admission. The fine-tune export mismatch remains a separate blocker.

Final verification (`final-validation.json`): all **255 historical report/sidecar pairs**, **1,008 artifacts**, and **47 original state/log files** still match the recovery inventory. The original directory still has exactly 510 report/sidecar JSON files; no frozen inference was added. Phase-1 manifests/protocol and the original Phase-3 freeze remain unchanged.

Full relevant regression command:

```powershell
Research/omr/.venv/Scripts/python.exe -m pytest Research/omr/tests Bridge/tests -q -o addopts=''
```

Result: **161 passed, 2 skipped, 9 subtests passed**, with the expected unreadable-clef music21 warning (`regression-tests.log`). New coverage verifies completed failures, missing/corrupt/partial results, unchanged originals, admission thresholds, continuous-pressure reset/expiry, and pending outcomes after simulated resource/session interruption even if a staged result exists. Stage-2 sample selection, general screening resume/duplicate protection, and scoring tests are not claimed here. `git diff --check` passed with existing line-ending notices. Research-only changes; no desktop publish was required.

### Evidence and reproduction

- [Recovery audit](reports/screening/stage1-20260926/recovery-v2/audit.json): exact freeze, primary/secondary audit hashes, per-item report/sidecar hashes, pending IDs, and preservation inventory.
- [Resource and runtime preflight](reports/screening/stage1-20260926/preflight-v1.json): runtime/input/reference identities and 30-second admission sample. Rerun only into a new output file: `Research/omr/.venv/Scripts/python.exe Research/omr/screening_stage1_preflight.py --output <new-json-path>`.
- [Development summary](reports/screening/stage1-20260926/development-v1/summary.json), [final validation](reports/screening/stage1-20260926/final-validation.json), and [resume process check](reports/screening/stage1-20260926/resume-check.json).
- Recovery reproducibility: `Research/omr/.venv/Scripts/python.exe Research/omr/screening_stage1_audit.py --output <new-evidence-directory>`. Check live workers first. Both recovery and preflight commands perform no candidate inference.

## Initial state (historical; superseded by Stage 1 evidence above)

- Historical Phase 3 full evaluation was interrupted during primary shipped-HOMR inference. Its last recorded output is item 255/402, with stale sequence state and 255 report/identity pairs. Their post-freeze artifact hashes have not been verified. The earlier 402/402 and 611/611 reference audits passed. Check current processes and logs before relying on the old no-worker observation.
- The old run's exact freeze, commands, log paths, stale PIDs, and partial directory are in [the interrupted handoff](PHASE3_HANDOFF.md), [the transfer handoff](PHASE3_EVALUATION_TRANSFER_HANDOFF.md), and [the job record](reports/phase3/job-record.md). These are evidence, not instructions to resume the old 20-stage sequence.
- The selected screening scope is 18 complete composition groups from frozen SMB pianoform pages, targeting about 60 pages. Four hours maximum per unattended session on this PC. Candidate priority: shipped HOMR, verified fine-tune, HOMR 455, Audiveris, corrected Zeus. PR #156 is conditional; Qwen/Rokot get a separate bounded development investigation after screening.
- `comparison-config-v2.json` and the old Phase-3 freeze describe historical planned or running configurations. Do not edit them to represent the new screen; create separately versioned identities.

## Stage-1 successor note (historical)

The Stage-2 action requested after Stage 1 is complete; see the Stage-2 record at the top for the current stop state and next action.

Before later candidate inference: recheck live processes/resources, reduce background RAM pressure, resolve or explicitly defer the fine-tune export mismatch, provision a pinned isolated 455 configuration, and validate each admitted configuration's resource limits. Stage 2 preparation is not authorization to begin Stage 3 inference. No later stage has been started.

After each stage, record start/end time, command and working directory, code/input/configuration identities, logs, completed/pending items, tests, and exact next action. Never infer a successful candidate prediction from an exit code or file count alone; follow the frozen failure policy.
