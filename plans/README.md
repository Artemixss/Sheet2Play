# Project plans

Start here to find a plan. This directory owns project execution plans; research
reports, artifacts and phase handoffs remain beside their evidence.

## Research plan entry point

[MAIN_PLAN.md](MAIN_PLAN.md) owns the selected **displacement correction** plan
(`2026-10-17-displacement-correction`): stop one measure's timing error from shifting
the rest of the score. The user approved it on 2026-10-17 and authorized Phase 1 only
(build the exact-label ruler and record baselines). Phase 1 baselines were recorded
on 2026-10-17, and Phase 2 waits on the user's review. The
[handoff](../Research/omr/reports/displacement/handoff.md) records state and the next
action.

## Other selected plans

| Plan | Status |
| --- | --- |
| [Current upstream exporter and run 480](2026-10-17-upstream-exporter-480.md) | Draft, a separate bounded task the user selected. Not yet authorized; it is independent of displacement. |

## Archived plans

| Plan | Lifecycle status | Completion / handoff evidence |
| --- | --- | --- |
| [HOMR 465 integration, library migration and local release](archive/2026-10-09-homr-465-app-integration.done.md) | **Completed**, Phases 1–4, 2026-10-17. 465 is the default with a 426 fallback; migration: 56 success, 1 failed, 2 unavailable | [Report (acceptance, delivery, rollback)](../Research/omr/reports/homr-465-app-integration/REPORT.md), [handoff](../Research/omr/reports/homr-465-app-integration/handoff.md) |
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
