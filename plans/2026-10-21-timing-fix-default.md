# TIMING FIX on by default, and no timing-fix or tempo labels on songs

**Plan ID:** `2026-10-21-timing-fix-default`
**Status:** Drafted 2026-10-21 at the user's request: converted songs should not say "timing fix"
or "tempo". TIMING FIX and the song's tempo should simply be the default, with no labels in the
UI or in file names. **Approved 2026-10-21** with D1-D4 as recommended ("approved, go with D1-D4
and start phase 1"). **Phase 1** (on by default) was checked and committed the same day
(`04614e6`; [Phase 1 result](#phase-1-result)). **Phase 2** (no labels, one row per song) was
requested the same day ("commit it and start phase 2"). It is shipped to `dist\Sheet2Play.exe`
and waits on the user's check and commit ([Phase 2 result](#phase-2-result)).
**Related:** [Remaining timing loss](2026-10-18-remaining-timing-loss.md) (shipped the fix, off by
default, and left "making the switch the default" out of scope),
[upstream 480 handoff](../Research/omr/reports/upstream-480/handoff.md) (its next action says the
default "still waits on the user's review"), and [per-song tempo](2026-10-19-song-tempo.md) (its
amendment makes printed tempo marks play by default).

**Precondition:** the per-song tempo amendment is committed in the main checkout first. Phase 2
edits `Program.cs`, `SongCache.cs` and `SongPackageTests.cs`, which that amendment also changes
(the `CustomTempo` block in `GetCachedSongsCore`). This plan does not touch `Program.Tempo.cs`,
`TempoDetection.cs` or `TempoMapStore.cs`. Line numbers below are from the main checkout on
2026-10-21, with that amendment still uncommitted.

## Why

The app announces things it should just do. The song's name gets a suffix
(`SongCache.TimingCorrectionLabel`, `" · timing fix"`), the playback header gets a **TIMING FIX**
badge, and the cached-song library adds **· tempo** to the length of a song that has its own
tempo. MP3, MIDI and MusicXML exports are named after the display name, so the suffix ends up in
file names too. The user's `exports\` folder has 16 files; 7 end in `· timing fix`, and
`Arrangement_ An Vo - Jane Doe` is there twice, once with the suffix and once without.

TIMING FIX is still off by default for new settings, but the user's own `settings.json` already
has `"timing_correction": true`.

## What exists today

| Where | What it does |
| --- | --- |
| `AppSettings.cs:326` | `bool TimingCorrection = false`, stored as `timing_correction`. `ReadOrRepair` rewrites an unreadable file with the record defaults. `UnmappedMemberHandling.Disallow` makes a file with an unknown field unreadable. |
| `Program.cs:779-786`, `1350-1363` | **TIMING FIX ON/OFF** pill on the home screen's engine row (`· HOMR only` when it does not apply). It is persisted and does not refresh the library list. |
| `SongCache.cs:368` | `TimingCorrectionLabel`, appended in `CreateLoadResult` (`:380`, MIDI-cache conversions) and `TryLoadRecentCore` (`:799`, legacy MIDI caches with a `timing_correction_sha256`). |
| `SongCache.Packages.cs:303` | `PackageResult` appends the label to the package's plain `DisplayName` whenever the interpretation is corrected. |
| `SongCache.Packages.cs:671-723` | `EnumeratePackageEntries` lists **one entry per package and timing setting**, so a PDF with both interpretations is two library rows. Only the suffix tells them apart. |
| `SongCache.Packages.cs:636-669` | `TryLoadPackageEntry` opens an entry with the timing setting **its manifest recorded**, not the current one. An uncorrected row plays uncorrected even with the switch on. |
| `SongCache.Packages.cs:596-620` | `RemoveStaleInterpretations` keeps the other timing setting's interpretation, so switching back is instant. |
| `Program.Score.cs:160-163` | **TIMING FIX** badge in the playback header. |
| `Program.cs:1026-1030` | **· tempo** after a cached song's length when `CachedSongEntry.CustomTempo` (the user's own tempo map) is set. |
| `Program.cs:1876`, `Program.Score.cs:244-254` | MP3, MIDI and MusicXML exports are named `<DisplayName>.<ext>` in `exports\`. `ExportMusicXml` says an export replaces an earlier one with the same name. |
| `Program.RenderAudio.cs:47` | `--render-audio` names its output after the source file, so it never carried the suffix. No change is needed. |
| `RecentSongsStore.Touch` | Replaces entries by `ManifestRelativePath` only. `recent.json` stores `display_name` with the suffix (9 of the user's 10 entries). The UI does not show these names: library rows take theirs from the loaded song, and recent.json only orders them by last opened. |
| `Program.Batch.cs:41` | `--convert-batch` already defaults to the fix on (`--no-timing-fix` turns it off). |
| `Program.Migration.cs:42`, `Program.Verification.cs:16` | `--reconvert` and `--verify-omr` run with the fix off (`--timing-fix` opts in). These are developer tools. |

The cache identities already separate the two settings, and this plan keeps them as they are.
The interpretation key hashes `timing_correction.py`, or `off` when the fix is off.
`interpretation.json` records `timing_correction`, and a corrected legacy MIDI cache is named
`.timing-<sha12>`. The plain name in `song.json` and in a legacy cache manifest never had the
suffix: it is added only when a song is loaded. So dropping it changes no identity and rewrites
no cache file.

**The user's library (read-only count, 2026-10-21):** 41 HOMR 480 packages and no 465 packages.
38 packages have a corrected interpretation and 5 have an uncorrected one; 2 have both
(*STYX HELIX* and *Daniel LITCH - Dexter Main theme*), so 3 have only an uncorrected one. The
remaining legacy MIDI caches (58 `homr465`, 59 `homr`, 3 `zeus`) include none with the fix.

## What turning it on by default costs

- **No OMR.** Recognition (`song.json`, `pages/`) does not depend on the fix. Each package with
  only an uncorrected interpretation is re-interpreted the next time it is opened, which takes
  seconds and is logged as `decision=reinterpret omr=false`. In the user's library that is 3
  songs. Legacy MIDI caches cannot be re-interpreted; they play as stored, as today, with their
  MIDI (LEGACY) badge and Re-convert action.
- **A known musical cost.** On HOMR 480, test-b 6222828 (a real meter change) scores 0.999 onset
  F1 raw and **0.361 with the fix**, because the fix anchors the meter change. The same score
  failed the timing plan's near-correct guard on 465 (0.995 to 0.952). Today such a song plays
  correctly unless the user turns the fix on. After this plan it plays the broken version unless
  the user turns the fix off, and with the labels gone nothing on the song says it was
  corrected. The overall gain is unchanged: against the previous fix, +0.074 onset F1 on 465 and
  +0.042 on 426, with 27 scores better and 4 worse on 465
  ([timing handoff](../Research/omr/reports/timing/handoff.md)). **Making the fix the default
  means accepting this trade.** The user accepted the candidate on 2026-10-18 but never decided
  on the default.

## Decisions (recommendations; the user confirms on approval)

- **D1. The toggle stays visible, on by default.** AGENTS.md requires a visible control for
  every user-adjustable setting. The switch is also the only remedy for a song like 6222828.
  It is a control on the home screen, not a label on a song, so it fits the request. Keep its
  wording and place. The alternative is to remove the setting and always apply the fix: that
  satisfies AGENTS.md by having no setting, but it leaves no remedy and needs the user's
  explicit choice.
- **D2. No settings migration.** Change the record default to `true`, so a missing field or a
  fresh or repaired file means on. An explicit `false` stays off, because that is a choice the
  file records. The user's file is already `true`. Do not add a version or marker field: with
  `UnmappedMemberHandling.Disallow`, an older build reading it would reset every setting to
  defaults. If the user wants stored `false` values forced on once, that needs such a marker,
  and the downgrade risk comes with it.
- **D3. Export names: plain `<song name>.<ext>`, replacing an earlier export of that name.**
  This keeps the rule `ExportMusicXml` already states. After Phase 2, one PDF with one engine is
  one song, whatever the fix, so the corrected and uncorrected conversions no longer need two
  names. The only clash left is one PDF converted with both 480 and 465. Those are already
  separate library rows under their engine headers, and today their exports already overwrite
  each other. The user has no 465 packages. The alternative is to add ` (2)` when the file
  exists, but then every re-export of the same song leaves another copy, which goes against the
  replace rule. The 7 old `· timing fix` exports stay as they are: they are the user's files.
  The next export of each song writes the plain name beside it.
- **D4. The current setting decides what plays.** The library shows one row per package, and
  opening a row or a recent entry uses the current TIMING FIX setting. This replaces the
  label-based distinction. The other setting's interpretation stays on disk, so switching back
  is still instant. The TEMPO panel is a control, not a label, and stays as it is.

## Phase 1: TIMING FIX on by default

**Scope:** settings default, tests, docs. No label changes yet.

1. `AppSettings.cs`: `bool TimingCorrection = true`. `ReadOrRepair`'s defaults pick it up from
   the record.
2. `Program.cs`: the toggle stays where it is (D1). Update its comment (`:779`).
3. `TimingCorrectionTests`: the first test asserts that an absent file or field means **on**,
   that an explicit `false` stays off, and that saving round-trips both values.
4. Docs: README (`off by default` to `on by default`); CONTEXT §3.5 if it describes the
   default; the timing and upstream-480 handoffs' next actions (the default is decided, with the
   6222828 cost recorded); the timing-loss plan's status line.

**Acceptance:**
- `dotnet test` passes, with the changed settings test.
- With `settings.json` deleted, the published app writes `"timing_correction": true` and the
  pill reads **TIMING FIX ON**. With an explicit `false`, it reads **OFF**.
- `scripts\verify-release.ps1` passes every step. Smoke snapshots `01-landing-*` show the pill ON.
- The user checks it in the app. Committing waits for their word.

### Phase 1 result

Implemented 2026-10-21 in the main checkout, on top of `de80db5`. Not committed.

- **Code:** `AppSettings.cs` now defaults `TimingCorrection` to `true`, and the doc comments on the
  record and `LoadTimingCorrection` say so. The toggle's comment in `Program.cs` notes the default
  and the remedy. The smoke harness (`Program.Smoke.cs`) sets `timingCorrectionEnabled = true`,
  because the smoke run never loads settings and the landing shots would otherwise draw the pill
  OFF.
- **Test:** `SettingIsOnByDefaultRoundTripsAndOlderFilesLoad` (renamed from `...OffByDefault...`)
  checks four cases. A missing file is written with `"timing_correction": true`. A file without
  the field loads as on. An explicit `false` stays off. Saving round-trips both values.
- **Docs:** README (on by default, and turn it off for a real meter change); the MAIN_PLAN status;
  the timing-loss plan's status line; the next actions in the timing and upstream-480 handoffs;
  the index. CONTEXT.md does not state the default and is unchanged. Historical lines saying the
  fix "shipped off by default" on 2026-10-18 are left as they are.
- **Evidence:** `dotnet test` passed 201 of 201. `scripts\verify-release.ps1` passed all 8 steps
  (lock, test suite, clean publish, asset manifest, runtime assets, 465 and 480 pins, launch) and
  verified `dist\Sheet2Play.exe`. Launching the published exe with `SHEET2PLAY_SETTINGS_PATH`
  pointing at an empty scratch folder wrote `"timing_correction": true`. `--smoke` rendered every
  screen, and `02-landing-populated` shows **TIMING FIX ON**. The user's own settings were not
  touched; they already had `true`.

## Phase 2: no timing-fix or tempo labels, one row per song

**Scope:** display names, the library list, recents, the badge, the tempo tag, exports. Cache
identities stay as they are.

1. **Names.** Delete `TimingCorrectionLabel` and its three uses (`SongCache.cs:380`, `:799`,
   `SongCache.Packages.cs:303`). The display name is the package's or cache's plain name.
2. **One library row per package.** `GetCachedSongs` takes the current timing setting.
   `EnumeratePackageEntries` yields one interpretation per package: the current setting's if it
   exists, otherwise the newest. For legacy MIDI caches with a plain and a `.timing-` file for
   one source and engine, list the one matching the setting. The user has none, so this is for
   correctness only. `Program.cs` passes `timingCorrectionEnabled` and refreshes `cachedSongs`
   when the toggle changes.
3. **Open at the current setting.** `LoadRecent` and `TryLoadPackageEntry` take the current
   setting when interpretation is allowed. An entry whose interpretation is for the other
   setting is re-interpreted (seconds, no OMR). Listing still never runs the interpreter: a row
   whose current interpretation does not exist yet is listed from the one it has, so its length
   may be slightly off until it is opened.
4. **Recents.** `RecentSongsStore.Touch` also removes entries pointing into the same package
   (`songs/scores/<engine>/<package>/`). Re-interpreting a song therefore leaves one recent
   entry, not two. When reading, strip a trailing ` · timing fix` from stored `display_name`
   values; the next touch rewrites them. The recent.json format is unchanged, with no version
   field.
5. **Badge.** Remove the **TIMING FIX** badge (`Program.Score.cs:160-163`). Keep MIDI (LEGACY)
   and the engine and CACHE badges: they describe the file and can be acted on.
6. **Tempo tag.** Remove **· tempo** from the library row (`Program.cs:1026-1030`). The length
   shown already follows the song's tempo. Then remove `CachedSongEntry.CustomTempo` and its
   assertions in `SongPackageTests`, since nothing else reads it.
7. **Exports.** No code change beyond the names: MP3, MIDI and MusicXML follow the display name
   (D3). Add a test that an export of a corrected package is named after the plain song name.
8. **Smoke.** `07-playback-score` no longer draws the badge (update its comment at
   `Program.Smoke.cs:217`). The landing snapshots use fixed sample names (`SampleCached`), so the
   tests above, not the snapshots, prove the names are plain.

**Tests to change or add:**
- `TimingCorrectionTests` (`:65`, `:78`) and `SongPackageTests` (`:191`): the corrected
  conversion has the **plain** name. Its `ManifestRelativePath` still differs (`.timing-`, or
  another `derived/<key>`), which proves the identities are unchanged.
- A package holding both interpretations lists **once**. The row follows the setting passed in,
  and opening it with the other setting re-interprets without running the pipeline (the fake
  pipeline's call count stays the same).
- Recents: touching a re-interpreted song replaces the entry for its old interpretation, and a
  stored suffixed name reads back plain.

**Acceptance:**
- `dotnet test` passes.
- `dist\Sheet2Play.exe --verify-library <dir>` on the user's library lists *STYX HELIX* and
  *Dexter Main theme* once each, and no row name contains `timing fix`.
- `scripts\verify-release.ps1` passes every step. Smoke snapshots `02-landing-populated` and
  `07-playback-*` show no suffix, badge or tempo tag.
- In the app: opening one of the 3 uncorrected-only songs re-interprets it in seconds and plays
  it corrected. Switching the fix off and reopening plays the uncorrected version. An MP3 export
  is named after the plain song.
- The user checks it in the app. Committing waits for their word.

### Phase 2 result

Implemented 2026-10-21 in the main checkout, on top of `04614e6`. Not committed.

- **Names:** `TimingCorrectionLabel` is gone. `CreateLoadResult` lost its `timingIdentity`
  argument and `PackageResult` its `timing` argument, since both were only used for the suffix.
  The legacy-cache path no longer appends it either.
- **One row per song:** `EnumeratePackageEntries(applicationDirectory, timingCorrection)` yields
  one interpretation per package: the switch's if it exists, else the newest.
  `GetCachedSongs(bool timingCorrection = true)` passes the switch down; the default keeps
  `MidiTester` compiling. Legacy MIDI caches are grouped by `RecentSongsStore.SongKey`, which
  drops the `.timing-` part, and the cache for the current setting is tried first. The app sets
  `timingCorrectionChanged` when the switch is clicked and relists the songs.
- **Open at the current setting:** `LoadRecent(entry, recordRecent, bool? timingCorrection)` and
  `TryLoadPackageEntry` play a package with the switch's setting, re-interpreting if needed.
  `null` keeps the entry's own setting. The app passes the switch; `--verify-omr`, `--reconvert`
  and the research tools pass nothing and behave as before.
- **Recents:** `RecentSongsStore.SongKey` gives every interpretation of a package one key (the
  package folder), and does the same for a legacy cache with and without `.timing-`. `Touch` and
  `Load` keep one entry per key. A stored name ending in ` · timing fix` reads back without it.
  The file format is unchanged.
- **UI:** the playback header's TIMING FIX badge and the cache playlist's `· tempo` tag are gone,
  and so is `CachedSongEntry.CustomTempo`. The smoke comment for `07-playback-score` is updated.
  CONTEXT §3.5 now says a package is one row and one recent entry whatever the switch.
- **Deviation:** there is no separate export-name test. The tests cannot reach `Program`, where
  the MP3, MIDI and MusicXML names are built from `DisplayName`. The plain-name assertions on
  corrected conversions (packages and legacy caches) cover what they are built from.
- **Tests:** 203 of 203 passed. Changed: `CorrectedAndPlainConversionsNeverShareACacheEntry` now
  expects plain names and one library row that follows the setting.
  `SwitchingTheTimingFixReinterpretsTheStoredPagesWithoutOmr` now expects one row, and opening
  that row with the other setting does not interpret again. New:
  `ASongOpensWithTheCurrentTimingFixAndIsReinterpretedWithoutOmr` (re-interprets, runs no OMR, and
  keeps both interpretations) and
  `RecentSongsKeepOneEntryPerSongAndReadOldNamesWithoutTheSuffix`.
- **Evidence:** `scripts\verify-release.ps1` passed all 8 steps and verified
  `dist\Sheet2Play.exe`.
  - **Library check:** `--verify-library` on the user's library lists 41 song packages, each
    once, all loading (43 rows before). *STYX HELIX* (`629a9d40…`) and *Dexter Main theme*
    (`7f5e9140…`) appear once each. No `song.json` name contains `timing fix`.
  - **Smoke:** the smoke run counts 100 cached songs (102 before) and renders every screen.
    `07-playback-score` has no TIMING FIX badge.
  - **Known failures:** the same check fails 61 legacy MIDI caches (58 `homr465` from profile
    `1fd5b26e…`, 3 `homr`). They went stale when 465 was re-pinned on 2026-10-19
    ([upstream-480 handoff](../Research/omr/reports/upstream-480/handoff.md)), and this phase did
    not change their validation.
- **Left for the user's check in the app:** opening one of the 3 uncorrected-only songs plays it
  corrected after a short re-read. Switching the fix off and reopening plays it uncorrected. An
  MP3 export is named after the plain song.

### Follow-up: the TEMPO button follows the song (2026-10-21)

Asked by the user after Phase 2 was committed (`fdb93b7`), with a screenshot showing
"TEMPO ♩=101 · 4 CHANGES" while bar 37 played at 111: "I want the tempo number dynamic in the
UI, so when it changes to 111 for example it should say it". This is in the same spirit: the
button now says what plays rather than the start tempo.

- `Program.Tempo.cs`: the button shows `SongTempoMaps.TempoAt(shown, bar playing)`. It falls
  back to the start tempo when the changes do not apply (CHECK BARS) or when no bar is playing.
  The controls right of it start at the widest the button has been for the song, so the open
  panel's row only ever moves right, and only once.
- Smoke: new `07-playback-tempo-playing` (paused in the last bar) shows **♩=186 · 2 CHANGES**.
  `07-playback-tempo`, paused in bar 2, still shows the start tempo of 110. README: the button
  shows the tempo of the bar playing.
- Not committed; it waits on the user's check.

## Out of scope

- Changing `timing_correction.py`, or fixing the meter-change fault behind 6222828. That
  belongs to the timing plan's follow-up.
- Renaming or deleting existing exports or cache files.
- Changing `--reconvert` or `--verify-omr` defaults. They are developer tools, and their recorded
  receipts depend on their flags. Recognition is the same either way.
- Eagerly re-interpreting the library. It happens per song on open, and a one-off pass can be
  added if the user asks.
