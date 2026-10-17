# Displacement correction handoff

Owner: [MAIN_PLAN.md](../../../../plans/MAIN_PLAN.md), `2026-10-17-displacement-correction`.

## Authorization

On 2026-10-17 the user approved the plan and authorized **Phase 1 only**: "approved do
small 465 then start displacement phase 1". The 465 integration closeout ran first and
is archived. Phases 2–4 each need their own request. Phase 1 includes the baseline
inference of shipped 465 and 426 on the new sets. Phase 1 changes no shipped code.

After reviewing the Phase 1 baselines the user authorized **Phase 2** on 2026-10-17:
"approved, start displacement phase 2". Phase 2 changes no code (research tooling only).

After Phase 2 the user authorized **Phase 3** on 2026-10-17 ("focus on finishing phase 3"),
asking that HOMR exporter source fixes be set aside as a separate matter. Phase 3 runs on the
research path only. The user's later order of work: remaining timing loss, then the frontend
and MusicXML-based playback (pedals, a MuseScore-like piano SFZ); none of it starts now.

## Phase 3 replan: started 2026-10-17

User decision, 2026-10-17: "go with option 1 then 2, approved for HOMR runs". Option 1 gates
the frozen correction away from real meter changes; option 2 repairs in-measure placement from
465's per-note page positions (`<!-- imgpos: x, y -->` on every note, already in the cached
pages). HOMR inference on new scores is approved. Shipped code is unchanged.

**New sets** ([displacement_heldout.py](../../displacement_heldout.py), receipts in
`phase3b/jobs/`). From the Phase 1 scan, never reusing a ruler score, short and medium bins:

- **dev-b** (20): songs by Phase 1 dev composers whose source writes more than one bar length,
  most polyphonic first, at most 5 per composer. For developing the gate; nothing held out.
- **test-b** (54): composers in neither Phase 1 split. Every bar-length-changing song (26 of a
  target 28: the whole pool) and 28 single-meter songs (at most 3 per composer). Held out.
- Test-composer songs stay unused, for option 2's held-out set later.
- Two MuseScore exit-1303 failures; 9 rejected in all. Manifest
  `phase3b/manifest.json`, SHA-256 `e7cd309d94f2d67f583b45a6b6b6cbe87d6e015b3ebea7bab5954512876e9d8e`.

**Deviation:** `Sheet2Play.exe` was republished after the Phase 1 capture (`55f4cab`, the
recent-songs store, frontend only). The capture never runs the executable, so the replan capture
requires Phase 1's bridge files and interpreter byte for byte and records both executable hashes.

**Pre-registered acceptance for option 1** (on test-b, scored once, after freezing on dev + dev-b),
each engine, gated variant against control: onset F1 gain with a 95% interval above zero; the
meter-change stratum's mean change at or above −0.01; pitch F1 change at or above −0.005; no
near-correct score losing more than 0.01. Stratum means are reported separately.

**Development (dev 40 + dev-b 20, before any test-b scoring).** Per-measure ledger
([displacement_meter.py](../../displacement_meter.py)): of the measures anchor-holes moves, a
harm (the label kept the decoded length) is most likely where two or more hole-free measures on
the page share the decoded length; with none, 753 fixes against 13 harms. Gates on voice
coverage, x inversions, measure width, the page's share at the meter and decisions per score did
not separate real one-off meter changes from errors. A new layout repair, **fit** (a measure
longer than the page meter whose late-started voices can all be moved back inside the bar), finds
overflows anchor-holes never touches, because a single late note leaves no hole.

| Onset F1 gain (95% interval) | dev 465 | dev 426 | dev-b 465 | dev-b 426 |
|---|---|---|---|---|
| anchor-holes (Phase 3 frozen) | +0.107 | +0.116 | +0.087 [−0.023, 0.186] | +0.080 |
| anchor-holes-keep3 | +0.116 | +0.114 | +0.096 [−0.013, 0.195] | +0.088 |
| fit + anchor-holes-keep3 | **+0.151** [0.083, 0.225] | **+0.126** | +0.077 [−0.035, 0.183] | **+0.090** |

On dev-b, 465's near-correct 5937814 (0.9995) loses 0.672 under every anchoring variant: one
real 9-quarter bar on a 6-quarter page, hole-marked and seen once, which no tested gate detects.
The pre-registered near-correct check is therefore expected to be at risk on test-b for 465.

**Pre-registered pair, chosen before scoring test-b:** primary **anchor-holes-keep3** (option 1,
the meter gate), secondary **fit+anchor-holes-keep3** (adds the first option-2 repair). Both are
scored once on test-b against the acceptance above; the primary decides option 1. 465's
position-based run placement (`place`) is recorded on development only: on spot checks it
moved almost nothing, because the fault Phase 2 called layout is mostly a voice started late
by a whole note, not notes out of page order.

**Capture** (launched 2026-10-17, working directory the repository root):

```
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/displacement/phase3b/jobs/capture-all-1 --max-seconds 14300 -- 'Bridge\.venv-homr-gpu\Scripts\python.exe' -I -B Research/omr/displacement_capture.py --manifest Research/omr/reports/displacement/phase3b/manifest.json
```

Smoke (`jobs/capture-smoke-2`, 6018965): both engines ok, peak 71% RAM (66% idle with other
apps open). Resume rules are Phase 1's: rerun with a new `--output`; finished items are skipped.

- `jobs/capture-all-1`: refused at start, an identity-check bug in the new code (fixed).
- `jobs/capture-all-2` (3,910 s, exit 2): 75 runs ok, then the app's own 465 guard stopped
  test-b 6239101 with `RESOURCE_STOP` (physical RAM 85.0%). Cause: research analysis run beside
  the capture on a machine idling at 66–81% with other apps open. The stopped attempt is kept in
  `data/displacement-ruler/failed-attempts/phase3b-resource-stop/`. dev-b is complete (40 runs);
  test-b has 72 runs left. Not retried automatically: resume with `--output .../capture-all-3`
  only when idle RAM is well below 75%, with nothing else running.
- `jobs/capture-all-3` (954 s, exit 2): 20 more runs ok, then the 465 guard stopped test-b 6575466
  on **VRAM** at 90%: a game (tModLoader) held about 5.2 of the GPU's 6 GiB. Peak RAM 64%.
  Attempt kept as `failed-attempts/phase3b-resource-stop/homr465-6575466-vram`. Left: 26 test-b
  scores (52 runs, about 50 minutes). Resume with `--output .../capture-all-4` when the GPU is free.

## Phase 3 status: test scored 2026-10-17, not accepted, replan

Write-up: [phase3/REPORT.md](phase3/REPORT.md). The frozen correction, **anchor-holes**
(`displacement_correct.py`, commit `a0c6bcc`), re-anchors a measure to the page meter only where
a voice leaves a hole between notes. Test set, scored once: onset F1 +0.158 [0.072, 0.252] on 465
(0.461 → 0.618) and +0.131 [0.054, 0.212] on 426, pitch unchanged. But on 465 one near-correct
score (5052787) loses 0.546, and the four test scores with more than five time signatures lose on
average (−0.164 on 465, −0.201 on 426), so the plan's accept fails and its replan trigger fired.
Single-meter scores gain +0.205 (465) and +0.172 (426). The test set is spent for this plan.

## Phase 1 status: started 2026-10-17, baselines recorded 2026-10-17

### Decisions and deviations recorded at start

- **Engraving path.** The plan names `build_dataset.py`. That tool is a training-data
  generator: even its clean variant writes JPEG pages at a random quality. The app's
  real inputs are born-digital MuseScore PDFs. The ruler therefore reuses
  `build_dataset.py`'s MuseScore helpers and its label-first rule, but writes a PDF.
  It exports the PDF and the MusicXML label from a single MuseScore job, so both come
  from the same in-memory score.
- **Piano-part extraction.** Each Lieder score is exported to MusicXML. Every part
  except the single two-staff piano part is removed, along with the original system
  and page breaks, so MuseScore lays out the piano part afresh. The piano-only file
  is then engraved.
- **Exclusions.** The test set must not reuse scores this project has already measured
  on. Excluded:
  - every OLiMPiC score: OLiMPiC is drawn from Lieder, and its test partition holds
    the canary;
  - the 21 Lieder scores already converted under `data/openscore/lieder/labels`, which
    are inputs to earlier frozen and diagnostic sets.
- **Training overlap, a known limitation.** Upstream HOMR training used
  `lieder + grandstaff + primus + pdmx + musetrainer`
  ([FINDINGS](../diagnosis/FINDINGS.md)). So both engines saw Lieder music during
  training, although never these piano-only full-page engravings. Absolute F1 on this
  ruler is likely optimistic. Corrections are compared paired against the same
  recognitions, which limits but does not remove the effect. PDMX, the plan's replan
  fallback, has the same overlap.
- **Inference path.** Baselines run the shipped bridge code from `dist/Bridge`: the
  app's PDF renderer, the per-page engine call (`run_homr465_page`, or `run_homr` for
  426), then `normalize_musicxml` and `combine_score_pages`. Each page's raw engine
  MusicXML is kept, so Phases 2–3 can rerun on cached output without inference.

### Progress

The tools are [displacement_ruler.py](../../displacement_ruler.py) (scan, select, engrave,
freeze), [displacement_capture.py](../../displacement_capture.py) (shipped-engine capture)
and [displacement_score.py](../../displacement_score.py) (baseline scoring). Each job ran
under the supervisor, with its receipts in `phase1/jobs/`.

- **Scan** (`jobs/scan`, 19.5 s). Of 1,352 Lieder scores, 1,069 are voice-and-piano
  candidates. Excluded: 200 OLiMPiC scores and 19 existing pairs (the other 2 are also
  OLiMPiC), 35 with non-vocal parts and 29 without exactly one two-staff piano part.
  Measure quartiles are 32 / 47 / 70.
- **Pilot** (`jobs/engrave-pilot`, six scores, 24 s). Piano-only engravings run 300–900
  notes a page. The library's median is 286 notes a page (465's own output, 56 scores),
  so the Lieder parts are **denser, not sparser**, and the plan's replan trigger does not
  fire. Denser pages mean fewer of them: only 36 candidates have 2,000 or more notes, and
  piano-only Lieder rarely exceeds 6 pages. The plan's 2–12 page range cannot be filled
  at the long end. **Deviation:** length is binned by note count against the library's
  multi-page scores: under 1,000 notes 39%, 1,000–2,000 28%, 2,000 or more 33% (n=46).
  Targets are short 20, medium 24 and long 36 (every long candidate). Every item still
  needs at least 2 pages.
- **Selection.** Each bin is ordered by multi-voice measure fraction, with a seeded hash
  breaking ties. Short and medium are capped at 5 per composer. Dev and test are split
  by composer, so no composer appears in both.

- **Freeze** (`jobs/freeze`). 80 items: dev 40 (short 10, medium 14, long 16) and test
  40 (short 10, medium 10, long 20), with 15 composers each side. Pages: 2 (36), 3 (19),
  4 (12), 5 (8), 6 (3), 8 (1), 10 (1). Six rejected: four single-page and two MuseScore
  re-import failures (exit 1303). Every label normalizes; the normalizer drops grace notes
  on both sides. Manifest SHA-256 `d640f889b2ac5c52e4416e439ecf861ed2cf3e746bcdfe87961cdaa41698093c`.
- **Worker cap (user decision, 2026-10-17).** The first smoke capture of shipped 426
  failed with ONNX "bad allocation" in its CPU PaddleOCR title detector. The 4 GiB
  per-worker job limit caused it; the system peaked at 52% RAM. That attempt is kept
  under `data/displacement-ruler/failed-attempts/`. At the user's request the supervisor
  now has no per-worker cap by default, and the 85% stops and commit reserve remain.
  The app's own per-page 465 guard in `Bridge/execution_safety` is shipped code and is
  unchanged.
- **Smoke** (`jobs/capture-smoke`, `jobs/capture-smoke-nocap`, dev score 5079459, 2 pages).
  465 had onset F1 0.4156 and oracle 0.8296 (ramp shape); 426 had 0.0512 and 0.7050,
  span 1.48 (global offset). The peak was 55% RAM and 50% commit.

### Full baseline capture (launched 2026-10-17)

```
Research/omr/.venv/Scripts/python.exe -B Research/omr/guarded_execution.py --output Research/omr/reports/displacement/phase1/jobs/capture-all-1 --max-seconds 14300 -- 'Bridge\.venv-homr-gpu\Scripts\python.exe' -I -B Research/omr/displacement_capture.py
```

The working directory is the repository root. Captures go to
`data/displacement-ruler/captures/<engine>/<id>/`, and `result.json` is written last.
The script stops itself after 13,500 s with exit 3. To resume, rerun the same command
with a new `--output` (`capture-all-2`, and so on); finished items are skipped. A
directory without `result.json` is an interrupted attempt: inspect it and move it to
`failed-attempts/` before resuming. Never retry a pressure stop automatically. After all
160 captures, run `displacement_score.py` (supervised), then record the baselines here.

### Baseline results (2026-10-17)

**Capture** (`jobs/capture-all-1`, 10,649 s, exit 0, no stop). All 160 engine×score
results exist: 158 from this job and the two smoke items it skipped. Failures: 426 on
5079629 (no MusicXML written), 465 on 5866060 and 4978478 (`AssertionError` inside HOMR).
All three are `NORMALIZATION_FAILED`, ordinary failures that score 0.0 under the protocol.
Peak was 56% RAM and 57% commit.

**Scoring** (`jobs/score-baseline`, then `jobs/score-baseline-2` after a change that only
makes error paths repo-relative, so no Windows user path is tracked; summaries are
identical). Output: [phase1/baseline.json](phase1/baseline.json). The 884 normalizer
"invalid note timing" warnings are the labels' grace notes (905 `<grace>` elements before
chord grouping), dropped as noted under Freeze. Test was scored for the baseline only.
Nothing was tuned on it, and it stays held out until a Phase 3 correction is frozen.

Composition-macro F1, failures counted as 0. "Oracle" is onset F1 after each 16-quarter
window takes its own best offset, fitted against the truth: a ceiling, not a result.

| Split | Engine | Pitch+onset+dur | Onset | Pitch | Oracle onset | Failures |
|---|---|---|---|---|---|---|
| dev (40) | 465 | 0.3295 | 0.3513 | 0.9226 | 0.6893 | 1 |
| dev (40) | 426 | 0.2965 | 0.3123 | 0.9166 | 0.6331 | 1 |
| test (40) | 465 | 0.4403 | 0.4606 | 0.9615 | 0.8530 | 1 |
| test (40) | 426 | 0.3976 | 0.4216 | 0.9791 | 0.8055 | 0 |

Paired 465 − 426 (composition bootstrap, 10,000 resamples, fixed seed):

| Split | Primary | 95% interval | One-sided p | Oracle onset |
|---|---|---|---|---|
| dev | +0.0330 | [−0.0457, +0.1164] | 0.213 | +0.0562 [−0.0139, +0.1200], p 0.053 |
| test | +0.0427 | [−0.0572, +0.1420] | 0.207 | +0.0474 [−0.0256, +0.1090], p 0.091 |

465 scores higher on 25 of 40 items in each split. Neither split shows a gain distinguishable
from zero. Pitch is read well (0.92–0.98) and timing is where the loss is.

**Drift.** Per-window offsets lift onset F1 by a mean of 0.34 (dev) and 0.39 (test) per
successful recognition. The shuffled control lifts only 0.08 to 0.15 (dev) and 0.11 to 0.17
(test). So, as on OLiMPiC, most of the timing loss on this ruler is displacement, not
misread rhythms. Shapes (successful items, dev / test):

| Shape | 465 dev | 426 dev | 465 test | 426 test |
|---|---|---|---|---|
| global offset (one shift recovers the score) | 15 | 13 | 19 | 18 |
| scatter | 12 | 14 | 5 | 7 |
| flat | 6 | 5 | 7 | 7 |
| steps | 5 | 5 | 7 | 4 |
| ramp | 1 | 2 | 1 | 4 |

Median span ratio is 1.00–1.05, so total length is nearly right. "Global offset" is the
largest group: a single constant shift recovers the whole score, which points at an error
at or near the start (the plan lists pickups and meter) rather than steady accumulation.
This is a lead for Phase 2, not a finding. Dev is harder than test (more scatter): the
splits are by composer, and the two sides differ in style.

**Bins** (pitch+onset+dur, 465 / 426): dev short 0.492 / 0.290, medium 0.294 / 0.292, long
0.259 / 0.304; test short 0.559 / 0.309, medium 0.280 / 0.283, long 0.461 / 0.499. The bins
hold 10 to 20 items each, too few to read as a trend.

**Speed** (page seconds p50 / p95): 465 23.2 / 35.8 (dev), 23.7 / 41.6 (test); 426 15.7 /
23.7, 16.4 / 34.6.

**Limits.** Both engines trained on Lieder music (see Decisions), so absolute F1 is likely
optimistic. Corrections must be compared paired on these same recognitions. The oracle
column is fitted against the truth.

### Phase 1 acceptance

- Engraved manifest frozen with hash: **done**.
- Baselines recorded for the engraved set: **done** (above).
- Library MusicXML check set: **not started, needs the user.** It is optional for the
  engraved ruler but is the plan's only real-world direction check. Until it exists, the
  "every library XML passes the match check" criterion has nothing to check.
- Replan trigger (Lieder sparser than the library): **did not fire** (denser, see Pilot).

### Not started

- User library MusicXML check set: waiting on the user's downloads into
  `%LOCALAPPDATA%\Sheet2Play\reference-xml\`. Optional for the engraved set.

## Phase 2 status: complete 2026-10-17

Full write-up: [phase2/REPORT.md](phase2/REPORT.md). Ledger: [phase2/ledger.json](phase2/ledger.json).
Tools: [displacement_attribution.py](../../displacement_attribution.py) (attribution, run under
the app's interpreter) and [displacement_evidence.py](../../displacement_evidence.py) (426 log
index, measure views, crops). Tests: `tests/test_displacement_attribution.py` (12 pass); the full
Bridge + research suite passes under the supervisor (`phase2/jobs/regression`). Final run:
`phase2/jobs/attribution-final`, 347 s, every recognition reproduced the app payload note for
note and undoing every mechanism puts every note in place.

- **Accepted:** named mechanisms account for 100% of displaced notes on dev, and every family
  above 2% of displaced notes has at least two verified examples (page crop, MusicXML, and 426
  tokens), except lost page, which occurs once.
- **Headline:** **layout**, HOMR's MusicXML placing notes wrongly while the tokens are mostly
  or entirely right, is 52% (465) and 49% (426) of displaced notes, in 32 and 31 of 39 scores.
  Fixing it alone moves 465's notes-in-place from 0.32 to 0.54. Tuplets are 12–13% (missing,
  two-note tremolos read as plain notes, and in 426 HOMR's `_fix_over_eager_tuplets` heuristic).
  Garbled measures 7–9%, page rounding 5%, dropped systems 3–4% (plus about 490 notes never
  decoded), repeat expansion 1–3%.
- **Deviations from the plan's mechanism list.** Meter errors (#161/#167) are real (HOMR
  computes the numerator as the page median) but cause little displacement directly: without
  re-timing a written meter cannot change a measure's length, so meter counts only where 426
  re-timed (0.8%). Pickups cause about 1%. The plan's "stitching at page boundaries" is page
  rounding (5%). New mechanisms the plan did not list: layout, tremolos, dropped systems, pages
  split into parallel parts, page-wise repeat expansion, the exporter's right-barline forward
  repeat, and the 426 bridge's page reuse.
- **Found and handed off, not fixed:** `bridge.select_generated_output` reuses the previous
  page's MusicXML when HOMR 426 writes nothing for a page (5902873, page 2). Offered as a
  separate task.
- **Known gaps:** "in place" is measure-level, not onset F1; 465 logs no tokens, so its tuplet
  losses cannot be split between the model and the stripping heuristic; the Phase 1 scan missed
  repeats stored on the vocal staff (manifest unchanged).

## Next action

**Needs the user: a replan decision for Phase 3.** The options in the Phase 3 report are: gate
the correction to pages without real meter changes, which needs a blind meter-change detector
and a fresh held-out set (new scores from the 1,069-candidate scan, which means new captures,
that is, inference the user must approve); repair the layout fault properly from note positions
(465's `imgpos`) or the exporter fix set aside earlier; or the user's library MusicXML check
set as the held-out direction check. Nothing ships until a variant is accepted (Phase 4).
