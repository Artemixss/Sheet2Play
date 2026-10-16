# Pinned HOMR 465 runtime

HOMR465 is the default after the main plan's development and installed-app gates
passed. HOMR426 remains available in the visible selector and error recovery.

`homr465-profile.json` pins local source revision
`33baa326900faa12702df8c4bdcbea034a3d6a34`, the 465 FP16 encoder/decoder, segmentation
308 FP16, processing settings, dependencies and Bridge code. The native launcher
uses no title detection, CUDA, 300-DPI PDFs and 8/1 ONNX threads. It validates every
declared file and dependency before inference and rejects provider/import drift.

Use the existing `Bridge/.venv-homr-gpu/Scripts/python.exe`. A fresh environment
requires the pinned versions in `requirements-homr465.txt`, including PyMuPDF for
PDF rendering and psutil for
the portable Windows supervisor. Install dependencies explicitly before setup;
inference never downloads assets or silently switches to CPU/426. This machine
reused its already-local dependencies and model bytes.

Provision from a local checkout of the pinned source and the three local model
files using `setup_homr465.py --source --encoder --decoder --segnet`, supplying
one filesystem path after each option. The setup checks hashes before copying
into `Bridge/.runtime/homr-465`, refuses conflicting existing files, preserves
upstream LICENSE and verifies the completed profile. Published Bridge contains
this external runtime and requires no Research imports. Preserve 426 site-packages
and model caches. Model payloads and environments are excluded from Git.

The upstream source is Christian Liebhardt's
[HOMR repository](https://github.com/liebharc/homr/tree/33baa326900faa12702df8c4bdcbea034a3d6a34),
declared AGPL-3.0. Its unmodified LICENSE and package attribution are retained in
the external source directory. Use that exact commit, rather than a current
branch. The three filenames in the profile are upstream ONNX checkpoint assets
under `https://github.com/liebharc/homr/releases/download/onnx_checkpoints/`.
Their full SHA-256 values are recorded in the profile and checked by setup.
Provision Python3.11 x64, install `requirements-homr465.txt` into the managed
GPU environment, acquire the exact source/model files explicitly, then run setup.
The provisioner copies only the declared source files and weights; the installed
recognition path blocks implicit downloads. CUDA requires a compatible installed
NVIDIA driver; missing CUDA fails explicitly. This implementation reused local
bytes and incurred no downloads or cloud charges.

Bridge schema2 uses `homr465` with required source/model/profile identities;
`homr` retains its legacy426 meaning. A frontend hash mismatch rejects the profile.
Changing profile contents requires deliberate regeneration and a matching frontend
pin, fresh qualification and release. Do not edit frozen research configurations.

New465 caches use full source and profile SHA-256 values. Existing426 versions and
retained PDF/images remain available. Use both `SHEET2PLAY_HOME` and an absolute
`SHEET2PLAY_SETTINGS_PATH` for scratch runs. Native job logs/resource receipts live
under the selected library's `omr-jobs`; retain failed receipts for diagnosis.

For a retained HOMR library, the published EXE accepts:

```powershell
dist\Sheet2Play.exe --reconvert inventory C:\absolute\inventory.json
dist\Sheet2Play.exe --reconvert resume C:\absolute\inventory.json C:\absolute\journal.json
```

Inventory reads only legacy HOMR manifests and source hashes, counts complete PDF
pages, and records missing sources. It never recognizes pages. Resume uses the
normal465 app/cache path, preserves426 entries and sources, validates committed
MIDI/profile identities, and maps successful recent references without changing
their order or timestamps. Failed/unavailable items remain accounted for; completed
successes are validated and reused. Resource, CUDA, identity, filesystem or deadline
failures interrupt the batch with pending work retained. Resume requires the same
inventory, profile and executable. Keep the journal and per-page job receipts local;
they can contain private paths. Run substantial batches through the recorded
supervisor with its four-hour maximum. Legacy `--reconvert Homr` remains an explicit
forced legacy rescan; use inventory/resume for this migration.

Windows containment retains 4GiB worker/commit reserve, 16 processes, 85% RAM/commit
stops and a bounded deadline. GPU admission/monitoring stops at90% VRAM. Pressure
or identity failures require review before another job. The observed aggregate
recognition improvement does not eliminate the known extra A5 in `three_voices`,
the `tuplet_aligned` regression or the independent-voice tie limitation.

Execution status and acceptance evidence:
[main plan](../plans/MAIN_PLAN.md),
[handoff](../Research/omr/reports/homr-465-app-integration/handoff.md).
