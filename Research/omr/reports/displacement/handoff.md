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

### Not started

- User library MusicXML check set: waiting on the user's downloads into
  `%LOCALAPPDATA%\Sheet2Play\reference-xml\`. Optional for the engraved set.

## Next action

Build and freeze the engraved candidate manifest, then validate one representative
score end to end before the full baseline runs.
