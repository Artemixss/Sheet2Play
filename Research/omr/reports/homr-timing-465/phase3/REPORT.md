# Phase 3: 465 regression diagnosis and playback readiness

**Complete with qualifications, 2026-10-08.** Owner:
[MAIN_PLAN.md](../../../../../plans/MAIN_PLAN.md), `2026-10-06-homr-timing-465`.
Authorization covered Phase 3 only. Phase 4, training and production adoption
have not started. [Acceptance ledger](acceptance-ledger.md), [current handoff](../handoff.md).

## Result and next decision

Pinned native 465 is ready for a **qualified research-only trial decision**.
Both musical regressions have artifact-grounded first-error traces. Existing app
Python dependencies, native fixed-token export and actual downstream conversion,
MIDI and controller checks pass within the stated scope. A demonstrated C# direct-XML
revision-validation defect received one isolated branch repair. Recognition remains
imperfect and full installed-app integration is not ready or claimed.

Recommend a separately authorized Phase 4 review of a bounded no-title 465 trial
versus retaining shipped HOMR. A trial/integration plan must name candidate model
paths, launch/title policy, cache/revision identity and admission checks before
execution. No automatic adoption, crop experiment, training or shipped-exporter
fallback follows from this report.

Phase 2's frozen composition-macro pitch/onset/duration F1 remains **0.5313290603**
for candidate versus **0.4139483028** for fresh control, delta **0.1173807575**,
bootstrap 95% interval **[0.0240277078, 0.2202143270]**, one-sided exact/Holm
**p=0.0174827576** for the single frozen claim. These support observed-screen
superiority, with unknown training overlap and no untouched-confirmation claim.
No score, claim or screen-selected setting changed in Phase 3.
[Phase 2 acceptance](../phase2/REPORT.md), [development review](../phase2/development-review.md).

## Demonstrated errors and bounded causes

| Regression | First demonstrated error | Later behavior / repair decision |
| --- | --- | --- |
| [three_voices](three-voices-diagnosis.md) | Extra A5 at beat 0/duration 4 already in raw tokens; crop retains the intended seven notes | XML/normalization preserve eight events; no downstream-created A5 and no justified recognition heuristic. F1 stays 0.9333333333 vs control 1.0 |
| [tuplet_aligned](tuplet-aligned-diagnosis.md) | One stacked bracket row disappears between span debug and decoder crop; lower raw durations are 1/2 rather than 1/3 beat | Native sounding-note-end clock compresses onsets and measure to 5/2 beats; normalization preserves XML. Exact crop operation and recognition mechanism remain unverified. F1 stays 0.125 vs control 1.0 |

`upper2/lower2` are additional voices on existing staves. The native four-position
fixture passes in both interpreters and through actual conversion/playback.
MusicXML voice IDs are per-staff interval allocation, not persistent transformer
position identities; malformed recognized durations can require extra layers.
All 12 cached generated exports replay identically apart from omitted engraving
coordinates, and all 12 normalizations reproduce frozen timed events.

No software cause supports widening crops, replacing durations or transplanting
#171/#178. Both fixes are already in pinned native source. Avoid correcting
recognition by inserting authoritative reference values. Remaining recognition
errors are qualifications, not a requirement for indefinite Phase 3 repair.

## Minimal repair and validation

Original `OmrPipeline.Run(...MusicXml...)` reaches valid published Bridge JSON,
then fails because `GetEngineRevision` rejects MusicXml. The research profile adds
one `MusicXml => "direct-xml"` branch; it links all other frontend sources unchanged.
[Repair identity](runtime-repair.json), [runtime/playback report](runtime-playback.md).
It changes no transcription or normalization, so there is no separately selected
or rescored 59-page candidate profile. Production sources and executable are not
published or edited. Full default XML runtime/model/cache contracts remain a
separate integration limitation.

| Check | Result |
| --- | --- |
| Native fixed-token replay | 12/12 in shared interpreter, 12/12 in app interpreter; native imports and nine declared dependencies compatible in each |
| Cached normalization / exact research MIDI | 12/12 preserved; tie_across_barline's intended merge is the only literal-to-normalized multiset difference |
| Actual published Bridge → research C# → cache MIDI → controller | 32/32 inputs: 12 candidate XML, 11 paired sources, nine known-correct/limitation fixtures |
| MIDI rounding | At 480 ticks/quarter, max onset 0.0008928571 s, duration 0.0005955714 s; within tick bound |
| Focused timing/tie/Bridge fixtures | 56 passed |
| Full Research/Bridge regression | 417 cases, 2 skipped, zero failures/errors |
| Fresh repaired-research frontend regression | 74 passed: all 69 existing tests plus five revision/schema/boundary cases |
| Preservation audit | 7,630 Phase 2 files, 98 protected/pinned entries and 38 snapshotted production source files unchanged |

The independent-voice production tie limitation remains six events rather than
four in its known reproducer. No production tie patch was made. Title-on behavior,
fresh installed-runtime GPU inference, candidate execution inside the installed
EXE and physical audio remain unverified. The calibrated 0.055-second offset is
unchanged. See the [met/unmet/unverified ledger](acceptance-ledger.md).

## Execution and preservation

Only cached evidence and existing packages were used. All substantive jobs used
the recorded Windows supervisor: 85% RAM/commit stops, 4 GiB reserve and aggregate
worker cap, 16 processes, one worker and bounded deadlines. No GPU inference,
new downloads, training, cloud spending, GUI/library change or release gate.
No agent Git command was issued; external Git telemetry is informational only.

Six failed receipts remain: sandbox canonical-path access, a new probe's chord
ordering assertion, original C# revision failure, omitted test friend-assembly
source link, VSTest connection timeout and a premature final-audit link check
against its not-yet-created preservation output. Each failure boundary was inspected
before the changed attempt. The last timeout's initiating cause remains unverified;
direct execution of the freshly built test DLL with approved localhost access
connected and passed. None was a recorded resource-pressure stop. Earlier Phase 2
interruption evidence remains frozen.

[Job record](job-record.md) records commands, runtime/input identity, output paths,
deadlines and failure diagnoses. [Audit](audit.json) verifies receipts, tests,
repair scope, replay/input identities, documentation links and frozen-file hashes.
At closeout no owned worker or research lock remains. Next action is the user's
Phase 4 decision authorization; this report does not grant it.
