# Sheet2Play Piano OMR Research Harness

An offline experiment area for measuring and improving recognition accuracy. It does not integrate
with Raylib, the production bridge, production caches, or `OmrPipeline` — nothing here runs when the
app runs, and nothing here changes what the app does until a measured result is deliberately
promoted into `Bridge/`.

The one thing it shares with the app is the engine itself: `src/sheet2play_omr/engines.py` invokes
`Bridge/bridge.py` as a subprocess, because HOMR lives in `Bridge/.venv-homr-gpu` rather than in
this directory's `.venv`.

---

## Read this first

**Canonical Stage 4 is complete:** the [evaluation and decision](reports/screening/v1/stage4-evaluation/REPORT.md)
recommends retaining shipped HOMR and no accuracy-led challenger confirmation now.
The historical 343-page remainder is partly previously inferred; the review records
exposure limits and optional runtime estimates. A later confirmation, Stage 5,
training or production change needs a separate request.

Consult the historical
[Phase 1](PHASE1_HANDOFF.md) and [Phase 2](PHASE2_HANDOFF.md) handoffs, and the
[Phase 2R correction handoff](PHASE2R_CORRECTION_HANDOFF.md) for prior evidence;
the [original Phase 2R handoff](PHASE2R_HANDOFF.md) remains historical. The old
full Phase 3 run was interrupted and is superseded by the selected screen.
[FINDINGS.md](reports/diagnosis/FINDINGS.md) preserves historical measurements.
This file covers the harness. The following observations are historical diagnostics,
not a candidate ranking or a replacement for the current plan:

- HOMR reads **pitch** well (F1 ~0.96) and places notes **in time** badly (onset F1 0.585 on the
  canary, 0.661 after the shipped fixes). The cause is measured: polyrhythm, not tuplets.
- On whole multi-page scores, most of what looks like scattered timing is **displacement** — a
  transcription that is musically correct but shifted. The scoring metric matches onsets by exact
  absolute equality with no alignment, so one extra beat early in a score costs everything after it.
  Correcting for it moves whole-score onset F1 from 0.5206 to 0.7714.

**Superseded proposal:** use the old headroom/displacement estimates to decide the next
training run. The current comparison leaves the separate fine-tune unchanged and selects
settings on development data. Alignment-assisted improvements are diagnostic, not headline scores.

The old `instructions_remote.md` runbook is absent from this checkout. The existing
[training setup script](setup_training.sh) is implementation reference, not authorization
to start or restart training.

---

## Transcoda was removed permanently

An earlier version of this README documented Transcoda as the harness's engine: a pinned AGPL
checkout, hash-locked weights, a private `bridge.py --engine transcoda` path, and a promotion gate
written against its numbers. **All of that is gone and must not be restored, even to fix a broken
import.**

Three tracked files are its leftovers and are inert:

| File | State |
| --- | --- |
| `setup_research.ps1` | **Do not run.** It clones Transcoda from git and throws unless `assets.lock.json` holds a Transcoda revision. See Environment below for how the venv is actually built. |
| `assets.lock.json`, `download_assets.py` | Pins and fetches the removed model. |
| `run_baseline.py`, `run_phase3.py`, `run_rhythm_experiment.py`, and the `infer` / `benchmark` / `prepare-dataset` / `materialize-dataset` / `train-adapter` subcommands in `src/sheet2play_omr/cli.py` | Still defined, but they route into the Transcoda runtime. |

Files under `reports/` keep their Transcoda mentions. Those are historical measurement records, not
instructions, and rewriting them would falsify the record.

The `smt_infer.py` / `smt_compat.py` pair is a different superseded evaluation — the Sheet Music
Transformer, measured and found not to beat HOMR. Kept because the DPI lesson in
the research notes came out of it.

---

## Environment

Python 3.11 (`pyproject.toml` pins `>=3.11,<3.12`). The venv is built from the lock files, not from
`setup_research.ps1`:

```powershell
cd Research\omr
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-inference.lock.txt
.\.venv\Scripts\python.exe -m pip install -e .
```

The dataset-generation and training extras are a second, larger layer — `verovio`, `CairoSVG`,
`augraphy`, `kornia`, `scikit-image`, `pyvips`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-training.lock.txt
```

Per the repository convention, each engine keeps its own virtual environment; do not merge this one
with `Bridge/.venv-homr-gpu`. Model weights, datasets and `.runtime/` are gitignored.

Tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

---

## The scripts that matter

### Diagnosis — where the error actually is

| Script | Purpose |
| --- | --- |
| `diagnose_rhythm.py` | Locate the HOMR rhythm error before paying for GPU time. The canary run: 100 OLiMPiC scanned systems, cached predictions, exact vs tolerant metrics, span ratio. |
| `diagnose_library_drift.py` | Decide whether the library's onset failure is displacement or genuine scatter. Free and repeatable — reads the payload cache `evaluate_library.py` writes. |
| `roundtrip_oracle.py` | Measure the ceiling a HOMR fine-tune could reach, without training anything. **Run this before proposing any fine-tune.** |

### Evaluation — scoring engines against ground truth

| Script | Purpose |
| --- | --- |
| `evaluate_library.py` | Score the engine on the app's own song library instead of a research corpus. About twenty minutes of GPU; caches every bridge payload under `reports/library/predictions/`. |
| `library_pairs.py` | Which library PDF is scored against which reference, and why. Backs a reviewed `reports/library/pairs.json`, which records the pairings that must *not* be made as well as the ones that hold. The file is written locally and not committed, since it names a personal collection. |
| `compare_engines.py` | Compare OMR engines on the same pages, with real numbers where ground truth exists. |
| `eval_zeus_on_olimpic.py` | Score the Zeus engine on the OLiMPiC canary. |

A typical displacement investigation is the two commands in that order:

```powershell
.\.venv\Scripts\python.exe evaluate_library.py --paired-only --variants patched
.\.venv\Scripts\python.exe diagnose_library_drift.py
```

### Corpus construction

| Script | Purpose |
| --- | --- |
| `build_olimpic_scores.py` | Rebuild whole multi-page scores out of OLiMPiC's single systems, with exact labels. The only whole-score ground truth this project has — per-system MusicXML carries consecutive measure numbers, so the systems tile the piece. |
| `generate_polyrhythm.py` | Generate targeted rhythm test cases that isolate HOMR's actual failure mode. Labels exact by construction. |
| `build_dataset.py` | Build aligned (page image, MusicXML) training pairs by engraving scores locally. |
| `notation_augment.py` | Inject notation-layer annotations into MusicXML before engraving, so a model must learn to ignore title blocks, fingerings and chord symbols. |
| `prepare_olimpic.py`, `slice_systems.py` | Prepare OLiMPiC samples; cut a score page into system images using a horizontal ink profile. |
| `download_openscore.py` | Fetch OpenScore CC0 corpora and convert them into aligned score/label pairs. Hash-verified against `openscore.lock.json`. |
| `download_smb.py` | Fetch the Sheet Music Benchmark, pinned to an exact revision. Gated; access granted. |
| `setup_training.sh` | Rebuild the training environment on the other machine. Needs WSL2 — the dataset converters use a Linux-only MuseScore AppImage. |

### Metrics

`src/sheet2play_omr/metrics.py` holds `calculate_note_metrics` and `span_ratio`.
`src/sheet2play_omr/omr_ned.py` adds OMR-NED, the metric published OMR results are quoted in.

**OMR-NED runs opposite to everything else — lower is better.**

Two cautions that have already cost time:

- `generate_polyrhythm.py`'s cases are **single-measure**, and both HOMR's tuplet heuristic and
  PR #146's re-timing compare a measure against the median of the others. Neither can fire there, so
  a flat result on that corpus is an artifact rather than evidence.
- Prefer MusicXML over MIDI as a reference. A MuseScore MIDI is the rendered performance with
  repeats expanded, so it will not align with the printed page the OMR reads — note counts differ
  from the transcription by 0.16x to 1.47x.

---

## Datasets

| Dataset | Size | On disk | Licence | Role |
| --- | --- | --- | --- | --- |
| OLiMPiC (scanned) | 2,931 systems, 200 scores | yes, 552 MB | CC BY-SA 4.0 | Real scans; robustness |
| OpenScore Lieder | 1,352 scores | lock file only | CC0 | Volume, where training runs |
| Generated polyrhythm | 11 cases | yes | own | The regression suite for rhythm work |
| Local library | 46 PDFs | yes | third-party | **The real evaluation target** |

OLiMPiC is derived from OpenScore Lieder — the same repertoire in two forms, not two corpora. Both
are voice-and-piano, so neither matches dense piano, which is what the app actually receives.

**Benchmark corpora do not predict this app.** OLiMPiC is scanned; the library is engraved MuseScore
PDFs. Upstream measures PR #141's tie recall at 0.93–1.00 engraved against 0.04–0.12 on scans, and
the first library song scored onset F1 0.921 where the canary average is 0.583.

Two datasets worth knowing about without running anything: upstream's benchmark release ships
`smb_homr.db`, HOMR's own predictions and expected output over 685 SMB pages. PDMX is the lawful
MuseScore corpus (250K scores, PDF+MIDI+MusicXML, ungated) and is already what HOMR trains on, so
scraping MuseScore would reproduce its training set.

---

## Licensing boundary

Sheet music under `Omr/` and `Research/` is sample material belonging to its respective owners.
OLiMPiC is CC BY-SA 4.0; OpenScore Lieder is CC0. HOMR is AGPL-3.0 and is installed into its own
virtualenv rather than redistributed. Vendored upstream code goes in `Research/omr/vendor/` and is
gitignored.
