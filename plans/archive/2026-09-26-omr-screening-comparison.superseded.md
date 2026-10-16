# Sheet2Play OMR comparison — selected screening plan

**Plan ID:** `2026-09-26-omr-screening-comparison`.
**Lifecycle:** Superseded as the execution queue by [the main plan](2026-10-03-zeus-attribution-repair.superseded.md)
on 2026-10-03; archived on 2026-10-04. Screening Stages 1–4 are complete,
with the [Stage 4 closeout](../../Research/omr/reports/screening/v1/stage4-evaluation/REPORT.md)
and [screening handoff](../../Research/omr/SCREENING_HANDOFF.md) preserved.
Stage 5 was not executed under this plan: the successor replaces its overall
four-hour/one-remedy proposal with staged Zeus/Rokot work. Confirmation and
promotion did not occur. The whole document is therefore `.superseded.md`,
not `.done.md`. Frozen evaluation contracts and dated evidence below remain
historical authority; old next-action statements are not the current queue.

Earlier retired proposals are also indexed: [exhaustive comparison](2026-09-26-omr-exhaustive-comparison.superseded.md)
and [HOMR extension](2026-09-26-homr-extension.superseded.md).

Selected by the user on 2026-09-26. **Status: historical comparison baseline; screening Stages 1-4 complete.** Current execution phases belong to [MAIN_PLAN.md](../MAIN_PLAN.md). This document retains the frozen comparison contracts and evidence; optional later comparison work still requires a request. The exhaustive-first Phase 3 sequence and separate Phase 4 HOMR extension plan are superseded. Their original text is recoverable under `.runtime/plan-retirement-20260926/`; the interrupted evaluation handoffs, frozen artifacts, and raw results remain evidence, not instructions to resume the old 20-stage sequence.

**Authorized provenance follow-up (2026-10-03):** the user supplied the
[main plan: Zeus attribution / timing repair / Rokot](2026-10-03-zeus-attribution-repair.superseded.md) and
requested execution of **Phase 1 only**. Its [provenance ledger](../../Research/omr/reports/zeus-attribution/phase1/REPORT.md)
and [job record](../../Research/omr/reports/zeus-attribution/phase1/job-record.md) own this follow-up.
The supplied plan replaces the proposed overall four-hour Stage 5/one-remedy limits
with separately reviewed repair phases; the four-hour unattended session and 90%
pressure policy remain. Later phases, rescoring, inference, training, cloud spending,
confirmation and promotion remain separately authorized actions. Historical screen
identities/results and Phase-1 evaluation contracts remain unchanged.

**Resource-policy update (2026-09-27):** The user raised the system-RAM admission and sustained-pressure threshold for future screening work from 75% to **90%** because this PC commonly idles around 70% RAM. Keep the 90% device-wide VRAM threshold and 30-second pressure window. The [new v4 screening manifest](../../Research/omr/reports/screening/v1/manifest-v4-3af78028afa2.json) records the 90% policy; the runner, preflight, development admission, and scorer use it. Existing screening manifests and reports retain their original 75% policy identity and measurements, and cannot admit new inference under the updated runner. New candidate development admission is required for v4. The frozen Phase-1 scoring protocol is a separate eligibility contract and is unchanged.

## Goal and boundaries

**Fine-tune readiness (2026-09-28):** Phases 1–3 of [the export repair plan](2026-09-28-homr-finetune-export-repair.done.md)
are complete: strict checkpoint/export parity, matching source/tokenizer provenance,
three local CUDA complete-page development passes and fresh admission under the
[verified v4 child manifest](../../Research/omr/reports/screening/v1/manifest-v4-502777eed80a.json).
The sample/scoring and 90% RAM policy remain unchanged. [The job record](../../Research/omr/reports/screening/finetune-export/job-record.md)
binds the repair evidence and commands. The user subsequently authorized corrected
fine-tune/455 screening prerequisites and **HOMR-only Stage 4**, now complete under
the [combined v4 manifest](../../Research/omr/reports/screening/v1/manifest-v4-e31f2e628e16.json).
The [final HOMR-only report](../../Research/omr/reports/screening/v1/2c98d5638c36/reports/homr-only-stage4-e35f73ca9f75/REPORT.md)
and [Stage 4 job record](../../Research/omr/reports/screening/v1/stage4-homr/job-record.md) preserve all
59 outcomes/scores per candidate and the paired analysis. Shipped HOMR remains the
descriptive leader among the three HOMR candidates; no HOMR challenger has supported
superiority. The user authorized Audiveris/Zeus and Stage 3 consolidation on 2026-09-29,
then paused before Zeus and later before consolidation. Those historical stops were
superseded by the latest request to finish Stage 3 on 2026-09-30.
**Stage 3 is complete:** all five candidates have 59 outcomes/scores on 18 complete
compositions, and the [consolidated report](../../Research/omr/reports/screening/v1/2c98d5638c36/reports/consolidated-stage3-836fb923bb33/REPORT.md) verifies all **295 result/score
pairs**, source summaries and declared artifact hashes. Primary F1 is 0.4061 shipped,
0.3844 repaired fine-tuned, 0.2857 corrected 455, 0.0986 Audiveris and 0.0228 Zeus.
Eight paired claims use composition bootstrap intervals, exact paired tests and Holm
correction; no challenger has supported superiority. The shipped/fine-tuned gap is
inconclusive. All sessions are closed; Zeus's historical scoring RAM interruption
was resolved without a model zero or omitted page. No inference/scoring was rerun
for consolidation. The [final audit](../../Research/omr/reports/screening/v1/stage3-cpu/consolidated-final-audit.json)
and [CPU job record](../../Research/omr/reports/screening/v1/stage3-cpu/job-record.md) preserve closeout
evidence and exact commands. **Canonical Stage 4 is complete (2026-09-30):** the
[evaluation and decision](../../Research/omr/reports/screening/v1/stage4-evaluation/REPORT.md) recommends
retaining shipped HOMR and no accuracy-led challenger confirmation now. Fresh audit
verified all 295 result/score pairs, 1,257 declared artifacts, full duration matrices
and eight paired claims; 14 focused fixtures and the 239-test research/bridge
regression passed (2 skipped, 9 subtests passed). Shipped/fine-tuned uncertainty
remains inconclusive. The [exposure audit](../../Research/omr/reports/screening/v1/stage4-evaluation/confirmation-exposure.json)
qualifies the historical 343-page "untouched" wording: 207 pages have prior shipped
outcomes, and only 135 pages/44 whole groups lack recorded prior attempts, with
composer/review/training limitations. No confirmation sample is selected or frozen.
**Next decision:** stop comparison, request bounded Stage 5/readiness work, or
authorize a preregistered confirmation after eligibility is resolved. Conditional/
unavailable configurations remain deferred pending readiness. No later execution
is authorized by this closeout; Stage 4 requirements below remain unchanged.
The [v5 CPU manifest](../../Research/omr/reports/screening/v1/manifest-v5-607ff64134da.json) pins a fully
readable local runtime inventory after sandbox access blocked bundled Java startup.
Every previously named package version and non-inventory source/model/input/parser
field matches; 33 additional readable metadata entries are disclosed. No package was
installed, historical freeze rewritten, scoring changed, or model tuned. The sample
and 90% policy are unchanged; fresh CPU development/admissions are required.
Stop before any untouched confirmation, Stage 5, training or promotion.

Obtain a useful, reproducible comparison quickly enough to guide the next investment. Start with shipped HOMR, the verified fine-tune, and upstream HOMR 455; then compare ready Audiveris and corrected Zeus. Use one bounded local PC session at a time. A smaller screen guides priorities but cannot by itself establish the original full-dataset ranking or authorize replacing the app model.

Phases 1, 2, and 2R and their frozen manifests/scoring rules remain unchanged. The old Phase 3 run stopped after 255/402 primary HOMR item reports, with stale `running` state and no live worker at the last verified handoff. **Check live processes and logs afresh before execution.** The 402/402 and 611/611 reference audits passed. Do not restart the old sequence; first verify and preserve its cached artifacts. No training, cloud spending, production promotion, or GPU migration is part of this plan. The existing $10 total cloud cap and local-private-library restriction still apply to any separately proposed future work.

The current development readiness review excludes the tested Qwen and Rokot complete-page configurations; do not count unavailable candidates as failures. LEGATO and MuSViT remain on the roadmap. **Upstream availability update (2026-09-29):** PR #156 is merged and model 465 weights are published; local source/weights/vocabulary/decoder verification and admission remain pending. See the [dated upstream audit](../../Research/omr/reports/diagnosis/UPSTREAM_AUDIT_2026-09-29.md). The current 455 release must not be treated as PR #156's multi-voice model. This status update does not authorize execution or change candidate order.

## Stage 1 — recover evidence and preflight the local PC

1. Inventory the old sequence, completion monitor, and candidate processes by executable, command line, PID, and creation time. Reconcile stale `running` state without launching another copy. Preserve the old state, logs, and incomplete item-256 raw directory. Verify all 255 completed reports, identity sidecars, and declared artifact hashes; include completed model failures. Record which outputs can be reused under exact identity and which cannot.
2. Reverify the Phase-3 freeze and 402/402 reference audit; preserve the valid 611/611 secondary audit even though this screen uses only primary pianoform pages. Do not change Phase-1 manifests, scoring protocol, original freeze, or historical reports.
3. Inspect Windows system/application events and resource history near the hard freeze. Record observed evidence and unresolved cause. Opening Opera GX during the run is plausible resource pressure, not proof of cause.
4. Run three development pages sequentially with the intended thread/resource limits. Time the complete path and inspect peak RAM, device-wide VRAM, CPU, logs, and free disk. Select no parameters from frozen benchmark predictions. Verify that each runtime, model file, input image, reference, and required permission is present before a long job.

Use one candidate worker and no concurrent scoring. Start each worker at below-normal process priority and cap CPU threads at half the logical processors wherever the specific runtime supports it. Monitor system RAM and device-wide VRAM every five seconds. In newly versioned screening runs, stop admitting new items at 90% RAM or 90% VRAM; if pressure persists for 30 seconds, end the current worker safely, retain its partial attempt, and mark that item pending for checked retry. Process at most five pages per chunk, with a four-hour cap per unattended session including scoring and orderly shutdown. A candidate's frozen timeout remains a scored failure; a session/resource interruption is pending, never scored zero. Do not infer per-process VRAM from device-wide readings.

## Stage 2 — freeze the screening sample and tooling

Use the frozen 402-page SMB pianoform collection. Select 18 entire composition groups by a deterministic SHA-256 sort of `20260926` plus composition ID: seven groups with 1–2 pages, eight with 3–4 pages, and three with at least five pages. The expected size is near 60 pages; the exact count is recorded before candidate scoring and may reach 79. Use existing manifest metadata only, never prediction quality or cached-output availability. Record feature coverage; investigate missing features on development fixtures rather than adding handpicked benchmark pages.

Write a separately versioned screening manifest with selected item IDs, composition groups, source/reference hashes, seed, selection algorithm, scorer/protocol hash, and candidate/configuration identities. Keep screening outputs separate from the original Phase-3 outputs. Provide distinct prepare, run, score, and report commands. Use atomic per-item completion, immutable identity sidecars, duplicate-worker protection, and resumable sessions. Scoring requires one completed outcome for every selected item. Preserve typed model failures under the frozen failure policy; incomplete attempts stay pending.

Historical predictions may be reused only after matching input, weights, source, preprocessing, decoder, normalization, and relevant environment identities and rechecking all artifact hashes. Record provenance. Recompute screening scores from verified results; never overwrite original reports or combine incompatible timing measurements. A changed candidate pipeline receives a new configuration identity.

## Stage 3 — run ready candidates in priority order

1. **Shipped HOMR** is the installed historical control and fallback.
2. **Fine-tuned HOMR** is the approval baseline after verifying checkpoint completion/provenance, exact weights, tokenizer/decoder, and the previously unresolved export identity. If final and development-selected checkpoints differ, record both and use development data for selection before frozen screening. Do not substitute an unverified export.
3. **HOMR 455** is a separate upstream pretrained configuration with pinned source, weights, decoder/tokenizer, precision, and runtime. Use an isolated research environment; do not update the app's HOMR environment.
4. **Audiveris** uses its validated native complete-page CPU route.
5. **Zeus** uses the corrected neutral complete-page CPU route, preserving detector, LMX, XML, stitching, and normalization evidence. Do not port it to GPU during this screen.

Each newly admitted configuration must pass relevant representation/conversion fixtures and a real complete-page development smoke before screening. If blocked, record the concrete missing artifact or failed gate and continue with the next ready candidate. Publish an interim HOMR report after entries 1–3 that actually run, then one consolidated report after entries 4–5. Run at most one candidate at a time and respect the session cap across restarts.

**Conditional additions:** The existing PR #156 candidate is **HOMR 465 (multi-voice)**, not an additional duplicate entry. Run it only after matching voice-aware weights, ordered vocabularies, decoder, and source are verified and development admission passes; use the same sample under its own identity. Investigate issues #161 (duplicate meter attributes) and #167 (mixed-meter numerator inference) only on development fixtures first. A demonstrated fix gets a separate pinned pipeline identity and comparable control. Test at most one HOMR-Combined configuration after compatibility is demonstrated; learned 455 weights and PR #156 weights cannot simply be combined. Defer unavailable combinations without starting training. PR #168's voice-specific slur-label fix and #166/#169's training-data changes remain future training considerations, not independently runnable inference candidates.

## Stage 4 — analysis and decision point

Use the unchanged Phase-1 scoring semantics: composition-macro pitch+onset+duration F1 as primary; pitch/onset and pitch-only F1, valid-output and failure-penalized OMR-NED, failed/empty/invalid/timeout counts, missing or extra notes, duration confusion matrix, majority baseline, balanced accuracy, and macro-F1. Merge sounding ties, preserve pickups, do not expand repeats for printed-page scoring, and do not shift or align predictions for headline numbers. Keep OLiMPiC systems and the private eight-page document out of complete-page screening claims.

Report paired differences against shipped HOMR and verified fine-tuned HOMR, composition-grouped bootstrap intervals, latency, cold start, resource use, training-overlap disclosure, and available feature breakdowns. Account for multiple tested superiority claims. Eighteen compositions have limited power for small gains; a narrow point estimate is inconclusive. Report recognition accuracy and practical suitability separately. Expose invalid or missing results, and never silently drop a difficult page.

After the consolidated screen, recommend which candidates merit a larger, untouched confirmation evaluation and estimate its runtime. **Stop for a new decision before that run.** The screen alone does not satisfy the existing promotion gate. Any later production proposal must meet at least +0.03 absolute primary F1 over verified fine-tuned HOMR with statistical support, no more than 0.01 pitch-F1 loss, no more than 0.01 increases in failure rate or failure-penalized OMR-NED, no demonstrated conversion/stitching corruption, and the frozen practical requirements. Also report against shipped HOMR; a worse fine-tune cannot displace a better shipped engine.

## Stage 5 — bounded Qwen/Rokot development follow-up

After the ready-engine screen, spend at most four hours inspecting existing Qwen/Rokot artifacts to separate recognition-format defects from conversion or page-joining defects. Permit one focused remedy to a demonstrated defect and validate it on the existing development controls, including a complete page. Do not use screening errors to tune these candidates or begin a broad prompt search. If a configuration passes the established readiness gates, propose a newly pinned future screen. Otherwise record its remaining blocker. LEGATO feasibility and MuSViT decoder availability remain separate roadmap questions.

## Required validation and handoff

Test deterministic selection and group integrity; disjoint screening and remainder groups; immutable originals; completed, failed, pending, corrupted, and cached outcomes; interruption/resume without duplicate inference; resource and four-hour limits under simulated pressure; and scorer agreement on identical fixtures. Run contract/unit fixtures, a representative development item, then the relevant complete research regression suite. Research-only changes do not require publishing the desktop app.

Record exact commands, working directory, manifests/hashes, logs, process identities, completed/pending items, and the next action before every long run. Update [the screening handoff](../../Research/omr/SCREENING_HANDOFF.md) and `CONTEXT.md` after each stage. The user can request one stage at a time in the same task; later stages should use recorded evidence instead of restarting earlier work.
