# Phase 3 interrupted execution handoff — 2026-09-25

**Lifecycle update, 2026-10-04:** Interrupted exhaustive comparison; execution sequence superseded on 2026-09-26 by bounded screening.
[Plans/status index](../../plans/README.md) identifies the owning historical
plan and its successor. Current research phases belong to [the main plan](../../plans/MAIN_PLAN.md);
dated next-step/stop statements below do not authorize new execution.

> **Historical execution handoff, superseded 2026-09-26.** The user's selected
> [screening comparison plan](../../plans/archive/2026-09-26-omr-screening-comparison.superseded.md) replaces the old 20-stage
> execution order. The logs, PID records, freeze, and cache details below
> remain evidence for recovery. Check live process state before any restart.

> **Evaluation transfer decision:** For the current counts, CPU/GPU findings,
> other-PC questions, and safe recovery sequence, read the focused
> [evaluation transfer handoff](PHASE3_EVALUATION_TRANSFER_HANDOFF.md).

> **Hard-freeze interruption, 2026-09-26:** The user reported that the PC hard-froze
> and asked questions before any evaluation restart. Read-only inspection found
> no live sequence, inference worker, or completion monitor. Sequence state still
> says stage 1 `primary_homr_page_infer` is `running` at old PID 26892, with 0/20
> stages complete. Its log ends at item 255/402; 255 report/identity pairs are
> present, plus a 256th raw directory without a report. These newly saved outputs
> have not yet been rehashed after the freeze. The old completion monitor PID 3292
> is also gone and produced no completion report. **Do not restart on either PC
> before reconciling this partial state, checking frozen identities, and deciding
> where the remaining evaluation should run.** Details are in the job record.

> **Active recovery, 2026-09-26:** The interrupted Phase 3 jobs were reconciled
> against the unchanged freeze and restarted. The primary audit is 402/402 valid;
> seven frozen entry checks had completed. All 76 saved primary HOMR item results
> rehashed and verified (75 succeeded, one failed outcome). The resumed HOMR stage
> passed item 107/402 at the last check. The secondary audit finished **611/611
> valid**, zero invalid; independent `verify_secondary_audit()` rehashed its
> references and images and accepted report SHA-256
> `50e5f6942eb2282c37fdecbf5c31b9bb7330224b794620baab1514eb9494b6fb`.
> It found 488 reviewed pedal-import warnings and no missing-voice-tag warnings.
> The audit and current HOMR stage logs had empty stderr. See the
> [job record](reports/phase3/job-record.md) for identities, preserved old evidence,
> exact commands, and log locations. The old process descriptions below are
> historical. Check the live state and logs before launching any process.

> **Resume checkpoint:** The only active Phase 3 job is the 20-stage sequence,
> launched from the repository root with `Research/omr/.venv/Scripts/python.exe
> Research/omr/phase3_sequence.py --freeze
> Research/omr/reports/phase3/phase3-config-freeze-v1-89f385c8790b.json`.
> Its launcher PID was 24440 and first-stage worker PID was 26892 at the last
> check. Read `.runtime/phase3/sequence-resume-20260926.{out,err}.log` and
> `.runtime/phase3/sequence/3fdd3d76aeab/state.json` before any restart; the
> current stage has its own `{stage}.out.log` and `{stage}.err.log`. Do not run
> another sequence while a matching worker is alive. After all 20 stages,
> validate every frozen summary, report the reduced roster and limitations,
> update this handoff and `CONTEXT.md`, then stop before Phase 4.

> **One-time completion monitor:** Hidden PID 3292 is waiting on the existing
> sequence. Its code and exact process identity are in the job record; logs are
> `.runtime/phase3/completion-monitor.{out,err}.log`. It will validate all 20
> stages and write the Phase 3 completion report and updated active links if the
> sequence finishes cleanly. It stops with an error if a stage fails or the
> sequence exits early. Inspect the monitor and sequence before restarting either.

> **Later read-only review, 2026-09-25 approximately 23:56 Europe/Istanbul:**
> [Progress review](PHASE3_PROGRESS_REVIEW.md) found the primary audit complete,
> configuration freeze written, seven entry commands completed, and primary HOMR
> inference logged through item 76/402. Secondary reference progress was 432/611.
> No matching Phase 3 workers remained active although sequence state said `running`.
> Treat the running-process descriptions below as historical; inspect and reconcile
> interruption state before resuming. This review did not launch or stop any job.

## Scope and current gate

The user authorized the reduced Phase 3 pretrained comparison described by the [readiness review](PHASE3_READINESS_REVIEW.md) and [canonical plan](../../plans/archive/2026-09-26-omr-screening-comparison.superseded.md). Phase 4 fine-tuned checkpoint evaluation, training, paired promotion analysis, and a shipped-app publish are outside this phase. **At this handoff update, no frozen candidate inference had started.** A running one-time bootstrap will start it automatically after the primary reference gate and frozen entry checks pass. Do not inspect frozen candidate predictions to change settings.

The ready roster is shipped HOMR complete page, Audiveris native page, Zeus neutral corrected page, and Zeus upstream on the separate annotated-system track. The review's other candidates remain deferred or excluded; do not score an omitted candidate as zero or claim an overall best engine.

## Completed preparation

- Phase-1 freeze, historical Phase-2 artifacts, frozen protocol, and approved roster were rechecked. The full research suite passed on 2026-09-25 after the current reference-builder fix; the focused reference suite has six passing tests.
- All 402 primary and 611 complete SMB page images were fetched and SHA-256 verified. The complete collection includes the primary 402 with matching image identities.
- HOMR page, Audiveris page, Zeus neutral page, and Zeus upstream system passed development entry checks under the current adapter configuration identities. The Zeus part join now uses stable IDs and passes a note-bearing preservation fixture.
- All 100 pinned OLiMPiC annotated-system images, MusicXML files, and canonical references passed the current canary audit. The current report is `reports/phase3/olimpic-canary-reference-audit-5382d5ffb4b3.json` (SHA-256 `1111a7f43ba8bb5901a9d21f99e217995522c576c4cb5ee9bbccf96c77b43b46`). The prior `8493bc91c9e5` report is historical evidence.
- `phase3_freeze.py`, `phase3_infer.py`, `phase3_score.py`, `phase3_olimpic.py`, and `src/sheet2play_omr/phase3_scoring.py` provide source-pinned freeze, resumable inference, and failure-penalized scoring. These have not yet been exercised on frozen candidate outputs.
- `phase3_sequence.py` defines 20 sequential local stages: primary inference/scoring for three page candidates, OLiMPiC system inference/scoring, secondary inference/scoring for three page candidates, and the three private diagnostic runs/summaries. It checks the freeze before launch, records the active child PID and logs, and stops on a stage failure for inspection. The bootstrap will launch this sequence after the seven frozen one-item checks pass.
- The single eligible, already-inspected local diagnostic PDF and symbolic reference matched their frozen SHA-256 values. Its eight pages were rendered once at 300 DPI and rehashed; the MIDI reference parses as 2,229 notes over 480 quarter notes. The ignored local preflight report is `.runtime/phase3/private-diagnostic/preflight.json` (SHA-256 `b1307979253a5274f44e2fd42ce76b257a3ce36df6badd314999664fe98e0dcb`); it contains no private names or source paths. The local runner can collect page results and a limited unaligned pitch-count diagnostic after the freeze.
- The SMB reference builder assembles frozen region **kern into complete-page MusicXML, checks exact sounding-note onset/duration after export, and normalizes to canonical events. An earlier builder produced 399/402 primary and 577/611 secondary valid references. All 34 of those secondary failures passed direct round-trip checks after the current fix, including empty trailing measures, long missing-staff rests, and music21-generated phantom ties. Older audits are diagnostic only.

## Running reference audits — leave intact

The current reference builder SHA-256 is `6e027f2195f355e0ea0ff4c09dbadb2bfc87049a05fa3131c85089d0d2cc481f`. Both audits were launched from the repository root with `Research/omr/.venv/Scripts/python.exe`; commands and immutable input identity are in the [job record](reports/phase3/job-record.md).

| Collection | Command suffix | PID | Output log | Required result |
| --- | --- | ---: | --- | --- |
| Primary 402 | `phase3_reference_audit.py --collection smb-pianoform` | 2812 | `.runtime/phase3/reference-audit-v5.out.log` | `reports/phase3/reference-audit-smb-pianoform-full-6e027f2195f3.json`, 402/402 valid |
| Secondary 611 | `phase3_reference_audit.py --collection smb-complete` | 24400 | `.runtime/phase3/smb-complete-reference-audit-v2.out.log` | `reports/phase3/reference-audit-smb-complete-full-6e027f2195f3.json`, 611/611 valid |

Check whether each process and report still exist before restarting anything. Their `.err.log` siblings hold errors. Reports and per-item references are write-once; a new builder revision creates a new identity. The primary 402/402 audit gates the configuration freeze and any frozen page inference. The secondary 611/611 audit gates secondary page inference.

The current OLiMPiC audit finished **100/100 valid** with 30 previously reviewed warnings. `phase3_freeze._olimpic_audit()` independently rehashed and accepted every artifact.

## Running one-time bootstrap — leave intact

`phase3_bootstrap.py` is running hidden as wrapper PID **14736**, Python worker PID **25200**. It is waiting on primary audit worker PID **18944** with verified creation epoch `1790364255.1055455`; its log `.runtime/phase3/bootstrap.out.log` confirms the wait, and `.runtime/phase3/bootstrap.err.log` is empty. The exact command, source hashes, log paths, and resume rules are in the [job record](reports/phase3/job-record.md). Do not launch another bootstrap or sequence while it is live.

After the primary audit finishes, this process verifies 402/402 references and warnings, writes the versioned freeze, runs seven one-item frozen entry checks, and starts the 20-stage sequential local evaluation. It stops on any gate or infrastructure failure. Inspect the bootstrap log, frozen preflight logs, and `.runtime/phase3/sequence/<freeze-hash-prefix>/state.json` before deciding what needs attention. The secondary 611-page audit continues independently; its gate is checked when the secondary sequence stages begin.

## Exact next actions

1. Inspect the two audit logs and the bootstrap log. The active process will freeze and begin the sequence if the primary 402/402 gate passes; do not duplicate it. If an audit is invalid, diagnose the source without candidate predictions and do not silently exclude eligible pages.
2. If bootstrap stops, read its stderr and the relevant frozen preflight or sequence stage logs. A stage marked `running` or `failed` needs process/output inspection before any retry. The sequence records exact commands, identities, and child PIDs.
3. When complete sets finish, review the failure-penalized composition-macro pitch/onset/duration F1, duration diagnostics, OMR-NED, latency, and resources. Keep primary SMB, secondary SMB, OLiMPiC system, and private diagnostic reports separate. The private diagnostic has no verified page-level timing split and reports only an unaligned pitch-count check, not a ranking result.
4. Update this handoff and `CONTEXT.md` with final evidence and limitations. No Phase 4/5 promotion claim follows automatically.

The repository already contained extensive unrelated modified and untracked work when Phase 3 began; preserve it. Research-only changes do not require the shipped release gate unless runtime behavior is changed.
