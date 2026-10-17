# Displacement correction handoff

Owner: [MAIN_PLAN.md](../../../../plans/MAIN_PLAN.md), `2026-10-17-displacement-correction`.

## Authorization

On 2026-10-17 the user approved the plan and authorized **Phase 1 only**: "approved do
small 465 then start displacement phase 1". The 465 integration closeout ran first and
is archived. Phases 2–4 each need their own request. Phase 1 includes the baseline
inference of shipped 465 and 426 on the new sets. Phase 1 changes no shipped code.

## Phase 1 status: started 2026-10-17

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

### Not started

- User library MusicXML check set: waiting on the user's downloads into
  `%LOCALAPPDATA%\Sheet2Play\reference-xml\`. Optional for the engraved set.

## Next action

Build and freeze the engraved candidate manifest, then validate one representative
score end to end before the full baseline runs.
