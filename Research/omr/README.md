# Sheet2Play Piano OMR Research Harness

This directory is a private, offline experiment. It does not integrate with Raylib, the production bridge, production caches, or `OmrPipeline`.

## Reproducibility and licensing boundary

- Transcoda source is pinned to `d4e2e687d5679ae96ca4aa6f01e06a5b338cd488` and remains AGPL-3.0-only.
- The released model is pinned to `b529f8aa5d996d9224df3395b5b92d0867343c91`.
- `model.safetensors` must match SHA-256 `c173a3b75b8a7558fa8670e9161b995c14ae879a5ea5ede91759dd9f403ee52a`.
- The ConvNeXt-V2 base model is pinned separately and hash-verified.
- Runtime code, model files, datasets, outputs, and the environment are ignored by Git.

Do not distribute the pinned Transcoda runtime inside a closed-source Sheet2Play build. Subprocess or directory isolation does not remove AGPL obligations.

## Setup

Setup is the only command that accesses GitHub, Hugging Face, PyPI, or the PyTorch wheel index:

```powershell
cd C:\Users\bur4x\Desktop\lecture\big_projects\Sheet2Play\Research\omr
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup_research.ps1
```

The default `Inference` profile installs only runtime, export, validation, and test dependencies. The later `Training` profile reuses the same environment and adds dataset-generation and adaptation dependencies:

```powershell
.\setup_research.ps1 -Profile Inference
.\setup_research.ps1 -Profile Training
```

Setup requires at least 14 GiB free. It creates `.venv` and `.runtime`, checks out the exact source commit, rejects modified or unlocked executable source files, downloads exact model snapshots, verifies every executable model file by size and SHA-256, installs PyTorch 2.9.1 CUDA 13.0, requires the RTX 4050, and runs an offline CUDA inference smoke test. Interrupted Git, `uv`, and Hugging Face downloads are resumable. Normal inference forces `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`; missing files fail instead of downloading.

## Inference

Beam width 3 and grammar-constrained decoding are separate benchmark modes. Grammar mode uses greedy decoding because the pinned Transcoda constraint stack is not beam-safe. On Windows, XGrammar uses its `torch_native` CUDA mask backend because native PyTorch does not ship Triton; model inference and grammar masking both remain on the RTX 4050.

```powershell
.\.venv\Scripts\python.exe -m sheet2play_omr infer C:\scores\piano.pdf --mode beam --output-dir .\artifacts\beam-run
.\.venv\Scripts\python.exe -m sheet2play_omr infer C:\scores\piano.pdf --mode grammar --output-dir .\artifacts\grammar-run
```

Each PDF is rendered at 300 DPI, then every page is normalized to the model's `1485x1050` canvas. The model is loaded once per document. Each prediction must emit EOS and pass strict two-spine Humdrum validation before the next page starts. Transcoda's page grammar permits an omitted final terminator, so the pinned semantic finalizer may append exactly one all-`*-` record when no content was trimmed and its spine rules prove the operation legal. Any other content change, incomplete tail, truncation, or invented split/join remains a hard failure.

A successful run writes page Kern, combined Kern, canonical events, schema-version-2 `OmrResult`, functional MusicXML, deterministic MIDI, and a run manifest. MusicXML and MIDI are parsed again before success is reported.

## Private production bridge

The application bridge can run the same pinned runtime directly, without a nested Python subprocess:

```powershell
cd C:\Users\bur4x\Desktop\lecture\big_projects\Sheet2Play
.\Research\omr\.venv\Scripts\python.exe .\Bridge\bridge.py --engine transcoda C:\scores\piano.pdf
```

This path loads one model per document, tries beam width 3 first, and lazily initializes grammar-constrained greedy decoding only when the current page fails Kern truncation, structure, or rhythm parsing. Runtime, CUDA, OOM, preprocessing, semantic, and export failures are never retried. Success `stdout` contains only schema-version-2 JSON; progress, diagnostics, and the final structured error record use `stderr`. Temporary Kern, MusicXML, and MIDI validation artifacts are deleted when the bridge call ends.

This remains a private local integration. Do not copy `.runtime`, `.venv`, or the AGPL source into application or publish output.

Verify three identical CUDA runs explicitly:

```powershell
.\.venv\Scripts\python.exe -m sheet2play_omr check-determinism C:\scores\piano.pdf --mode beam --runs 3
```

## Baseline execution

The deterministic smoke baseline verifies locked assets, runs beam and grammar inference on the committed piano fixture, calculates F1 metrics, checks three-run determinism for the selected decoder, and attempts a two-page real-PDF MusicXML/MIDI round trip:

```powershell
.\.venv\Scripts\python.exe .\run_baseline.py
```

The machine-readable results are written to `reports/baseline-smoke.json` and `reports/fixture-benchmark.json`. A nonzero exit means acceptance failed; do not clean the `uv` cache or begin adaptation after a failed baseline.

## Benchmark

The benchmark manifest is JSON Lines:

```json
{"id":"grandstaff-0001","kind":"system","image":"C:/benchmark/0001.png","ground_truth_events":"C:/benchmark/0001.events.json","homr_events":"C:/benchmark/0001.homr.events.json"}
```

Run both decoding policies:

```powershell
.\.venv\Scripts\python.exe -m sheet2play_omr benchmark .\data\benchmark.jsonl --mode both --output .\reports\baseline.json --require-acceptance-size
```

Only structurally valid modes are eligible. The harness chooses higher onset-duration F1, then lower latency. It records pitch/onset/onset-duration F1, offset error, staff accuracy, voice accuracy after optimal voice-ID alignment, structural validity, failure rate, latency, and peak VRAM.

## Dataset selection

The source manifest is JSON Lines with `id`, `source`, `musicxml`, `staff_count`, `instrument`, optional `composition_hash`, `license_conflict`, and structural `tags`. PDMX rows marked with a license conflict are rejected.

```powershell
.\.venv\Scripts\python.exe -m sheet2play_omr prepare-dataset .\data\sources.jsonl --output-dir .\data\splits --train-count 25000 --validation-count 2000 --test-count 2000 --require-fixture-coverage
```

Splitting occurs by composition hash before system sampling, preventing pages from one composition from crossing train, validation, and test sets. Required fixtures cover dotted rhythms, tuplets, ties, voices, dense chords, accidentals, repeats, cross-staff notation, and numeric tempo.

Image/target materialization must use the pinned Transcoda dataset-generation pipeline under `.runtime/transcoda/scripts/dataset_generation`. That upstream pipeline already provides canonical Kern normalization and synchronized Verovio rendering. Do not create image-only augmentations after target alignment. Restrict the selected sources to the official GrandStaff partitions and PDMX `no_license_conflict` data.

Invoke the pinned generator through the wrapper:

```powershell
.\.venv\Scripts\python.exe -m sheet2play_omr materialize-dataset .\data\splits\train.jsonl --output-dir .\data\materialized-train --workers 4 --seed 20260813
```

The wrapper creates a collision-checked hard-link staging area and runs the exact checked-out Transcoda generator with deterministic seeds, resumable run artifacts, coverage-oriented failure handling, and captured Verovio diagnostics.

## Adaptation gate and training

No training starts unless structural validity is at least `0.95`, pitch F1 is within `0.02` of homr, onset-duration F1 is at least `0.05` above homr, and estimated cloud cost is at most `$10`.

```powershell
.\.venv\Scripts\python.exe -m sheet2play_omr train-adapter `
  --train-manifest .\data\materialized-train.jsonl `
  --validation-manifest .\data\materialized-validation.jsonl `
  --candidate-summary .\reports\candidate-summary.json `
  --homr-summary .\reports\homr-summary.json `
  --output-dir .\artifacts\adapter `
  --hourly-rate 0.40 `
  --estimated-hours 12 `
  --max-runtime-hours 12 `
  --max-temperature-c 85
```

The trainer freezes the base model, inserts LoRA layers only into decoder linear layers, uses mixed precision, caps training at three epochs, validates every epoch, checkpoints adapter-only safetensors, stops early, checks the GPU temperature, and enforces a monotonic runtime ceiling.

## Promotion

The production enum remains homr-only until the candidate has 100% parseable nonempty output, pitch F1 at least `0.98`, onset-duration F1 at least `0.90` and `0.15` above homr, staff/voice accuracy at least `0.95`, exact structural fixtures, median latency below 30 seconds per page, peak VRAM below 5.5 GB, and identical outputs over three runs.

This harness makes that decision measurable. It does not imply Scan2Notes-level accuracy; the released Transcoda model itself reports a substantial synthetic-to-real domain gap.
