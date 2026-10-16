# Runtime and downstream readiness

Owner: [MAIN_PLAN.md](../../../../../plans/MAIN_PLAN.md), Phase 3 only, 2026-10-08.

## Existing runtimes

Both shared research and intended app HOMR interpreters are Python 3.11.9,
within pinned upstream's declared Python range. Every declared base/CUDA
dependency constraint passes in each interpreter, native `homr.main` imports,
and all 12 retained generated exporter inputs reproduce the cached musical XML.
See [shared evidence](runtime-shared.json) and [app-interpreter evidence](runtime-installed.json).
The app interpreter is `Bridge/.venv-homr-gpu/Scripts/python.exe`; the production
HOMR resolver finds this environment from the published Bridge location.

The scoring interpreter's music21 is **9.9.1**; the app environment's installed
music21 distribution is **10.5.0**. Identical 32-input conversion results establish
agreement on these fixtures despite that version difference, not equivalence for
all possible MusicXML. No environment was downgraded or replaced.

Installed checks include NumPy 2.4.6, OpenCV-headless 4.14.0.94, Pillow 12.3.0,
RapidOCR 3.9.2 and ONNX Runtime GPU 1.24.1. The constraints and remaining versions
are recorded individually. This is import/export and conversion compatibility,
not a new GPU inference/provider admission or proof that the launched executable
uses source/model 465. No dependencies, weights or OCR payloads were downloaded.

## Actual conversion, cache MIDI and controller

[Input manifest](playback-manifest.json): 12 cached 465 generated XML files,
11 authoritative generated XML sources, six existing golden Bridge builders,
one explicit pickup/tempo fixture, the four-position native exporter fixture and
the known independent-voice tie reproducer: **32 inputs**.

The [probe](../../../probes/homr465-playback/Program.cs) calls actual
`OmrPipeline.Run`, the published `dist/Bridge/bridge.py`, and the installed Python
interpreter. The published Bridge uses its normal repeat expansion and schema-2
JSON path. JSON matches the pinned normalizer's research expectations in pitch,
onset, duration, seconds, tempo, part, staff and voice identity for all 32 inputs.
Golden builders are independently checked against their retained note multisets;
pickup expectation is explicitly `(beat 0,duration 1,seconds 0/1)` followed by
`(beat 1,duration 4,seconds 1/2)` at the tempo change from 60 to 120 BPM.

The real `SongCache.WriteMidiForTesting`/`ReadMidiForTesting` helpers exercise the
same write/read code as production. All note counts and pitches survive. The real
`PlaybackSession`, `PlaybackClock` and `PlaybackController` run with controlled
time and captured MIDI output. Audio activity, visual activity, overlap/held-note
behavior, completion and silence pass at event-interval sample positions.
All sessions retain the calibrated **0.055-second** default; it was not changed.
See [32 results](playback-results-repaired/results.json) and individual JSON/MIDI.

XML timings use rational quarter-note units. Research music21 MIDI exports
preserve all 12 normalized generated event lists exactly. App cache MIDI uses
**480 ticks/quarter**, so sevenths are rounded: maximum observed onset error
**0.0008928571 s**, duration error **0.0005955714 s**, in the known-correct
septuplet source. Remaining sub-microsecond differences reflect integer MIDI
tempo/metric conversion. These pass the independently calculated tick bound;
they do not explain the aligned-tuplet half-beat durations or compressed measure.
MIDI/visual notes retain timing and pitch; staff/voice metadata is not a playback
identity field, although the Bridge JSON preserves it.

## One demonstrated minimal software repair

The original C# probe failed after successful Bridge conversion:
`ValidateResult` calls `GetEngineRevision(MusicXml)`, whose switch has no MusicXml
branch. [Before receipt and stack](jobs/playback-probe/worker.log).
The isolated [profile copy](../../../probes/homr465-frontend-profile/OmrPipeline.cs)
adds exactly `OmrEngine.MusicXml => "direct-xml"` in that revision switch.
[Identity/repair scope](runtime-repair.json), [after receipt](jobs/playback-probe-repaired/result.json).
The profile links unchanged frontend sources and package versions. It does not
change recognized notes, exporter, normalization, score rules or any Phase 2
output. No separately rescored 59-page profile is needed.

All 69 existing frontend tests plus five new revision/schema/boundary checks pass
against this fresh research assembly. The wrong revision and wrong schema remain
rejected; existing HOMR/Zeus revision contracts remain unchanged.
[TRX](frontend-test-results-diagnostic/phase3-frontend.trx).

This is explicitly selected-runtime ingestion, not complete default MusicXML
import. Default MusicXml runtime selection, model revision and cache settings
still have missing switch branches. The boundary tests execute the first two
missing contracts; `SongCache.GetOmrSettings` is confirmed by code inspection.
No full persistent-library cache, GUI launch or production import success is claimed.
Those unrelated contract additions were not silently bundled into this repair.

## Remaining limitations

- Known production independent-voice/chord/system tie handling yields **six**
  events where the isolated exact tie parser yields **four**. Its research tie
  fixtures and Bridge tests pass while preserving this documented limitation.
  Neither parser nor normalizer was transplanted into production.
- Native recognition limitations remain, including the two diagnoses and the
  other non-exact development controls recorded in Phase 2. Compatibility is
  not transcription correctness for those outputs.
- The candidate remains the **no-title** research profile. Native title detection
  is optional and disabled in the measured configuration; normal app launcher
  selection, candidate model paths, title policy and candidate/cache revision
  identity require explicit integration work before adoption. Title-on behavior,
  fresh installed-runtime GPU inference and installed-executable candidate use
  are unverified. Earlier title-OCR allocation failures remain historical evidence.
- Physical audio, synthesizer/output latency and perceived musical quality were
  not tested. The fake clock/output validates dispatch logic, not sound hardware.
- Training overlap, untouched generalization and source-versus-weight attribution
  remain unknown. Phase 2's supported screen gain is unchanged and qualified.
