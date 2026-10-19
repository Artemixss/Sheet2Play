# Phase 3 report: expressive playback

**Plan:** [`2026-10-19-musicxml-songs`](../../../../../plans/2026-10-19-musicxml-songs.md), Phase 3, requested
2026-10-19 ("commit phase 2 then continue with the next phase"). **Result: implemented and
shipped; every acceptance criterion met, with the tempo criterion met on a hand-written fixture
because no MusicXML of "Beyond This Station" is on this machine (below).** Committed after the
panel was made collapsible at the user's suggestion.
Evidence that lists private library paths (`library-after/`, `convert-fixture/`, `*.log`) and the
per-score tempo jobs (`tempo/jobs/`) stay local.

## What changed

- **`SongExpression.cs`** (new): the playing rules. Dynamics use MuseScore's velocities for the
  same marks (pp 33, p 49, mf 80, f 96, ff 112; sf/sfz 112 for one chord; fp drops to p after
  its chord), and a `<sound dynamics>` value wins when the score has one. A dynamic belongs to its
  part (both hands). A hairpin runs from the level at its start to the dynamic at its end (within
  one beat), or one step (16) further when there is none, and holds there. Staccato plays half the
  written length, staccatissimo a quarter, portato or staccato with tenuto three quarters; accent
  adds 16, marcato 24. A marked chord rolls upward 30 ms per note, every note ending as written.
  Grace notes play in written order just before the beat (a slashed one a 32nd, an unslashed one a
  16th), so the decorated note stays with the other hand. Pedal marks become CC64 changes on every
  pass of a repeat; a stop and a start at one place make a pedal change in either order.
  `ExpressionPlayback` applies the panel's switches to a loaded song; a MIDI file keeps its own
  velocities and only its pedal is switchable.
- **`SongPerformance.cs`**: `SongTimeline.Build` returns notes and pedal; with every switch off it
  is the Phase 2 timeline line for line. `MapPosition` keeps the place in the measure when Repeats
  changes; `BarTimes` serves the tempo check.
- **`Playback.cs`**: pedal events in the session, ordered at one time as pedal up, note offs, note
  ons, pedal down. The MIDI controller sends CC64, restores the pedal (and real velocities) after a
  seek or resume, and lifts it on pause, stop and song end. `IMidiOutput.SetSustain` defaults to
  nothing; `DryWetMidiOutput` sends `ControlChangeEvent(64, v)`. The `audioOffsetSeconds` default is
  unchanged (0.055).
- **`SoundFontEngine.cs`**: CC64 to MeltySynth at the event's sample; seek and resume restore the
  pedal, pause lifts it first so held voices do not ring through the pause. Sessions without pedal
  send nothing, so their audio is unchanged.
- **`SongCache`**: a song package's result carries its performance; a MIDI file's result carries
  the sustain pedal it records (`ReadMidiPedal`, one pedal down while any channel holds it).
- **EXPRESSION panel** (`Program.Expression.cs`): an EXPRESSION button bottom-left above Export
  MP3 opens PEDAL, DYNAMICS, ARTICULATIONS and REPEATS sideways, each ON/OFF, saved in
  `settings.json` (all on by default). At the user's suggestion the panel is closed at every start
  to keep the screen clean; the closed button says how many switches are off ("EXPRESSION · 1 OFF")
  so a switched-off pedal is never hidden. A switch the
  song has nothing for reads "· none" (HOMR reads no pedal or dynamics). A change rebuilds the
  session in place, keeping position, speed and play/pause. The header counts the notes played;
  Export MP3 renders the session being heard; `--render-audio` uses the saved switches, or
  `--no-expression`.
- **Verification**: `--verify-library` also checks that expression off reproduces each song's
  events and records what expression changes; `--verify-timeline` compares the app's timeline with
  a MIDI export of the same score. `Research/omr/expression_tempo_check.py` drives it with MuseScore
  4 and the fixture `Research/omr/fixtures/expression-tempo.musicxml` (written for this check).
- **Tests**: 22 new in `ExpressionTests` (139 in all, all passing); two render with the installed
  SoundFont.

## Acceptance

| Criterion | Result |
| --- | --- |
| The pedal state is correct at 100% of 1,000 random seek points on fixtures | **Pass.** A score with repeats, pedal starts, changes and a stop: 1,000 seeks through the MIDI controller (each followed by a random advance) and 1,000 seeks of the synth engine all leave the pedal at the value the change list gives for that time. |
| Offline render: voices held while CC64 is down and released when it lifts; without pedal the render equals Phase 2 | **Pass.** A half-second note with the pedal down until 2 s still has a voice at 1.9 s and none at 3.9 s; without the pedal none at 1.9 s. The rich fixture with every switch off renders sample for sample like the Phase 2 timeline. |
| Velocities ordered pp < p < mf < f < ff; hairpins monotone | **Pass.** 33 < 49 < 80 < 96 < 112; a crescendo from p to f rises from 49 to 96 without falling, a diminuendo with no target falls 16 and holds. On the fixture, MuseScore's own MIDI export agrees: velocity correlation 0.9998, mean difference 0.1. |
| A MusicXML with tempo marks: total length within 1% of MuseScore's MIDI export, bars within 50 ms | **Pass on the fixture; the corpus differs only where MuseScore stretches.** The fixture (tempo 72, 120, half note = 50, 60, with a repeat) matches MuseScore 4 exactly: every bar 0 ms, length 0%. The five exact labels with tempo marks match to the millisecond at every bar up to their first fermata or "rit."; after it MuseScore stretches and the app does not, as the plan decided (fermatas kept, not played), so their lengths differ by 0.3 to 1.8%. "Beyond This Station" exists in the library only as MIDI; the three MusicXML files in Downloads are Audiveris output without tempo marks. ([`tempo/summary.json`](tempo/summary.json)) |
| All expression off reproduces Phase 2's event list exactly; `audioOffsetSeconds` unchanged | **Pass.** Unit test on the rich fixture, and `--verify-library` on the whole library: all 90 playing songs give identical events with expression off, and none changed its notes or length since Phase 2. The default is still 0.055. |
| Release gate passes | **Pass,** 8 of 8 on the first run. |

## Library and fixture results

- **Library** (`--verify-library`, published exe): 151 songs, 90 play, 61 fail; the 61 are the same
  songs that failed before Phase 2 (58 stale HOMR 465 caches, 3 others), none for expression. 13 of
  the 26 custom MIDI files record a sustain pedal (1 to 396 changes) and now play it. The five HOMR 480 package entries
  (four songs, one also with the timing fix) have no pedal, dynamics or repeats (HOMR reads none of
  the first two); four have accents, so their velocities now vary.
- **Fixture through the published app**, in a throwaway library: imported as a song package,
  reopened from it, and rendered: 42 notes and 8 pedal changes with expression, 41 notes and none
  without (the grace note is the difference).
- **Pedal against MuseScore:** on the two corpus scores with pedal marks throughout, all 36 and 34
  changes land within 5 ms of MuseScore's. On the fixture MuseScore drops the pedal on the second
  pass of the repeat; the app pedals on every pass, as written.
- **Grace notes:** MuseScore also plays them before the beat, but for their full written value
  (an eighth, 0.5 s at 60); the app plays a 32nd. A style choice, not a timing error.

## Findings and limits

- Fermatas, "rit." and other gradual tempo changes are not played (plan: recorded for a later
  choice). That is the whole difference from MuseScore on the corpus.
- Seeking into a passage held only by the pedal does not re-strike the notes the pedal was
  holding; the notes still held by a key are re-struck, as before.
- `CONTEXT.md` is still not updated for song packages or expression; it has another chat's
  uncommitted edits.

## Next action

Phase 4 (SFZ piano) needs its own request. The user wants any C# engine rework as a separate
request at the end of the plan, before Phase 6.
