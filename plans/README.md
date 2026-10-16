# Project plans

Start here to find a plan. This directory owns project execution plans; research
reports, artifacts and phase handoffs remain beside their evidence.

## Research plan entry point

[MAIN_PLAN.md](MAIN_PLAN.md) owns the selected **HOMR 465 integration, library
migration, and local release** plan (`2026-10-09-homr-465-app-integration`). All
four execution phases are authorized by the 2026-10-09 implementation request;
Phases 1–2 are complete; Phase 3's batch finished with 56 successes, one failure
and two source orphans. The work was pushed on 2026-10-16; resume/audit and Phase 4 closeout remain pending at the selected
usage stop. The [execution handoff](../Research/omr/reports/homr-465-app-integration/handoff.md)
records the next action. The installed app and saved engine now select 465.

The completed predecessor and its [handoff](../Research/omr/reports/homr-timing-465/handoff.md)
retain the research evidence. The active plan records the user's later selection
of conditional 465 default adoption, a 426 fallback and recoverable-cache migration.

## Draft plans

Written 2026-10-17 for the user's review; neither is authorized for execution yet.

| Plan | Status |
| --- | --- |
| [Displacement correction](2026-10-17-displacement-correction.md) | Draft; becomes MAIN_PLAN once selected and the 465 plan is archived |
| [Current upstream exporter and run 480](2026-10-17-upstream-exporter-480.md) | Draft; separate bounded task selected by the user, independent of displacement |

## Archived plans

| Plan | Lifecycle status | Completion / handoff evidence |
| --- | --- | --- |
| [HOMR 465 and shipped-engine rhythm repairs](archive/2026-10-06-homr-timing-465.done.md) | **Completed with qualifications**, Phases 1–4, 2026-10-08; recommendation only, no production adoption | [Phase 4 report/ledger](../Research/omr/reports/homr-timing-465/phase4/REPORT.md), [proposed bounded trial](../Research/omr/reports/homr-timing-465/phase4/adoption-proposal.md), [handoff](../Research/omr/reports/homr-timing-465/handoff.md) |
| [Zeus attribution, shared timing repair and Rokot readiness](archive/2026-10-03-zeus-attribution-repair.superseded.md) | **Superseded**, 2026-10-07; Phases 1–2 and bounded Phase 4 complete, Phase 3 qualified, Phase 5/Rokot deferred | [Phase 2 independent closeout](../Research/omr/reports/zeus-attribution/phase2/closeout-20261004/REPORT.md), [Phase 3 report](../Research/omr/reports/zeus-attribution/phase3/REPORT.md), [Phase 4 acceptance/handoff](../Research/omr/reports/zeus-attribution/phase4/handoff.md) |
| [HOMR fine-tune export repair](archive/2026-09-28-homr-finetune-export-repair.done.md) | **Completed** Phases 1–4, 2026-09-28 | [Completion/job record](../Research/omr/reports/screening/finetune-export/job-record.md), [authorized Phase 4 closeout](../Research/omr/reports/screening/v1/stage4-homr/job-record.md) |
| [Bounded OMR screening comparison](archive/2026-09-26-omr-screening-comparison.superseded.md) | **Superseded execution plan**, 2026-10-03; screening Stages 1–4 completed 2026-09-30; old Stage 5 replaced by the now-superseded Zeus/Rokot plan | [Screening handoff](../Research/omr/SCREENING_HANDOFF.md), [Stage 4 decision](../Research/omr/reports/screening/v1/stage4-evaluation/REPORT.md) |
| [Exhaustive OMR comparison](archive/2026-09-26-omr-exhaustive-comparison.superseded.md) | **Superseded**, 2026-09-26; not completed as written | Completed [Phase 1](../Research/omr/PHASE1_HANDOFF.md), [Phase 2](../Research/omr/PHASE2_HANDOFF.md), [Phase 2R](../Research/omr/PHASE2R_HANDOFF.md) and [bounded correction](../Research/omr/PHASE2R_CORRECTION_HANDOFF.md); [interrupted Phase 3](../Research/omr/PHASE3_HANDOFF.md) |
| [Separate HOMR extension proposal](archive/2026-09-26-homr-extension.superseded.md) | **Superseded**, 2026-09-26; proposed scope was not completed as written | Replacement: [selected screening plan](archive/2026-09-26-omr-screening-comparison.superseded.md); later HOMR evidence is linked there |

The historical comparison remains the source for frozen evaluation contracts.
The [2026-10-07 Phase 1-only request](../Research/omr/reports/zeus-attribution/phase1/revalidation-20261007/REPORT.md)
reviewed the existing implementation; fresh revalidation stopped at resource
admission before any worker launched. Original phase statuses remain unchanged.
Its completed screen does not mean the optional follow-up, confirmation or
production promotion occurred. Handoff names remain stable; lifecycle notes at
their start distinguish completed work from superseded interruption records.

## Naming and maintenance

- Keep the current research plan in **MAIN_PLAN.md** with a stable plan ID.
- Store other explicitly selected project plans here under descriptive names;
  add their status and evidence links to this index.
- Archive whole plans as **archive/<plan-id>.done.md**, **.superseded.md** or
  **.cancelled.md** only when that outcome is supported. Completed phases do
  not make an unfinished whole plan done.
- Update this index, **AGENTS.md**, **CONTEXT.md** and the relevant handoff status
  when a plan closes or its current phase changes. Preserve dated evidence.
- Keep short redirects at old locations needed by historical links. Those
  redirects contain no competing instructions.

[Organization handoff](ORGANIZATION_HANDOFF.md) records this migration and its checks.
