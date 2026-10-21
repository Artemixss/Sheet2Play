# Per-song tempo: handoff

**Owning plan:** [`2026-10-19-song-tempo`](../../../../plans/2026-10-19-song-tempo.md)
**Phase status:** Phase 1 requested 2026-10-21 ("refresh the md files first then start phase 1").
It is **shipped, not committed** ([Phase 1 report](phase1/REPORT.md)).
- **Tempo:** "Beyond This Station" with the user's map plays 298.82 s against the MuseScore MIDI's
  298.82 s, with a median bar difference of 0.1 ms. It played 438 s before.
- **Regression:** with no map, all 129 playing library songs give identical events.
- **Checks:** frame-time p95 +1% to +5%; xunit 193; gate 8 of 8.

**Next authorized action:** the user checks the TEMPO panel in `dist\Sheet2Play.exe` and approves
the commit. Phases 2 (reading printed tempo marks, research) and 3 (shipping detected marks) each
need their own request.

## Where things are

- **Code:**
  - `Visualization_engine/TempoMapStore.cs`: the model, the store, and `SongTempoMaps` (override,
    seeding from the score, bar names)
  - `Visualization_engine/TempoInput.cs`: rules and the typed field
  - `Visualization_engine/Program.Tempo.cs`: the panel
  - `TempoOverride` in `SongPerformance.cs`
- **User data:** `%LOCALAPPDATA%\Sheet2Play\tempo-maps.json`, created on the first edit. None exists
  yet on this machine.
- **Evidence:**
  - tracked: [`phase1/summary.json`](phase1/summary.json)
  - local: `phase1/library-*/` and `phase1/timeline/`, which hold private paths and are gitignored,
    and `phase1/bench.log` and the two snapshots, which are ignored by the reports' `*.log` / `*.png`
    rules

## Rerunning the checks

- **Tempo against the MIDI** (working directory: repository root):
  `dist\Sheet2Play.exe --verify-timeline <package>\derived\<key>\performance.json "<library>\songs\midi\custom\HOYO-MiX, Mika Kobayashi - Beyond This Station.mid" out.json --tempo 110q,17=110q.,25=186q`
- **No-map regression:** run `--verify-library <new dir>` with two builds and compare the rows'
  `PlainEventsSha256` and `ExpressedEventsSha256`. The baseline was `HEAD` exported with `git archive`
  (a worktree fails on long research paths), with the new `Program.Verification.cs` copied in.
