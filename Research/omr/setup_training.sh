#!/usr/bin/env bash
# Set up a HOMR fine-tuning environment on a Linux box (native or WSL2).
#
# The vendored clone under Research/omr/vendor/ is gitignored, so cloning this repository does
# not bring the training tree or our changes to it. This script rebuilds both from scratch:
# upstream at a pinned commit, plus the patch in patches/, so a second machine trains the same
# thing rather than stock upstream - which would fix nothing, since the whole point is a data
# filter that upstream sets differently.
#
#   bash Research/omr/setup_training.sh              # set up only
#   bash Research/omr/setup_training.sh --smoke      # set up, then run the smoke test
#
# Everything lands under Research/omr/vendor/. Nothing outside it is touched.
set -euo pipefail

# Pinned so every machine trains identical code. Contains aa5c8ce, the fix for the
# zero-duration crash (upstream issue #136) that is still unreleased on PyPI.
HOMR_COMMIT="2d0c0a66b6ebc9a8b3e3e61b3a6be4b0e1701d97"
CHECKPOINT="pytorch_model_426-b6fd20809a8dcaf10dfd39a4ca4f64c6f056e644"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR="$HERE/vendor"
REPO="$VENDOR/homr"
PATCH="$HERE/patches/homr-training-sheet2play.patch"

log() { printf '\n=== %s ===\n' "$1"; }

log "Checking prerequisites"
for tool in git python3 curl; do
    command -v "$tool" >/dev/null || { echo "missing: $tool"; exit 1; }
done
python3 -c 'import sys; sys.exit(0 if (3,11) <= sys.version_info < (3,16) else 1)' \
    || { echo "homr needs Python >=3.11,<3.16; found $(python3 -V)"; exit 1; }
echo "python: $(python3 -V)"

if ! command -v nvidia-smi >/dev/null; then
    echo "WARNING: nvidia-smi not found. Under WSL2 the GPU comes from the Windows driver;"
    echo "         if this is WSL and nvidia-smi is missing, training will fall back to CPU."
else
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
fi

log "Cloning upstream homr at $HOMR_COMMIT"
mkdir -p "$VENDOR"
if [ -d "$REPO/.git" ]; then
    git -C "$REPO" fetch --quiet origin
    git -C "$REPO" checkout --quiet --force "$HOMR_COMMIT"
    git -C "$REPO" clean -qfd
else
    git clone --quiet https://github.com/liebharc/homr.git "$REPO"
    git -C "$REPO" checkout --quiet "$HOMR_COMMIT"
fi
echo "at: $(git -C "$REPO" log --oneline -1)"

log "Applying the Sheet2Play training patch"
# Raises convert_pdmx.py's complexity/track ceiling so dense multi-voice piano enters
# training, and fixes the fine-tune path, which upstream wires to the accidentals branch.
if git -C "$REPO" apply --check "$PATCH" 2>/dev/null; then
    git -C "$REPO" apply "$PATCH"
    echo "patch applied"
elif git -C "$REPO" apply --reverse --check "$PATCH" 2>/dev/null; then
    echo "patch already applied"
else
    echo "PATCH DOES NOT APPLY at $HOMR_COMMIT - upstream moved, reconcile by hand"
    exit 1
fi

log "Installing dependencies"
cd "$REPO"
if command -v uv >/dev/null; then
    uv sync --extra training 2>/dev/null || uv sync
elif command -v poetry >/dev/null; then
    poetry install
else
    echo "Neither uv nor poetry found. Install uv:  curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

log "Fetching the run 426 checkpoint"
mkdir -p "$VENDOR/checkpoints"
if [ ! -f "$VENDOR/checkpoints/$CHECKPOINT.zip" ]; then
    curl -L --progress-bar -o "$VENDOR/checkpoints/$CHECKPOINT.zip" \
        "https://github.com/liebharc/homr/releases/download/checkpoints/$CHECKPOINT.zip"
fi
mkdir -p "$REPO/training/architecture/transformer"
python3 - "$VENDOR/checkpoints/$CHECKPOINT.zip" "$REPO/training/architecture/transformer" <<'PY'
import sys, zipfile, pathlib
archive, destination = sys.argv[1], pathlib.Path(sys.argv[2])
with zipfile.ZipFile(archive) as z:
    for name in z.namelist():
        if name.endswith(".pth") and not (destination / pathlib.Path(name).name).exists():
            z.extract(name, destination)
            print("extracted", pathlib.Path(name).name)
PY

log "GPU capability check"
# bf16 needs Ampere (compute capability 8.0+). A Turing card - RTX 20xx, including the
# 2060 Super - cannot do it, and the trainer defaults to bf16. Those boxes must pass
# fp32=True, or be switched to fp16, or training will fail or silently misbehave.
python3 - <<'PY'
try:
    import torch
except ImportError:
    print("torch not importable yet; re-run this check after dependencies finish installing")
    raise SystemExit(0)
if not torch.cuda.is_available():
    print("CUDA NOT AVAILABLE - training would run on CPU and is not viable")
    raise SystemExit(0)
name = torch.cuda.get_device_name(0)
major, minor = torch.cuda.get_device_capability(0)
memory = torch.cuda.get_device_properties(0).total_memory / 1e9
print(f"{name}  compute {major}.{minor}  {memory:.1f} GB")
if major >= 8:
    print("bf16 supported -> default settings are fine")
else:
    print("bf16 NOT supported on this card (pre-Ampere).")
    print("  Run training with fp32=True, or change bf16 to fp16 in")
    print("  training/transformer/train.py TrainingArguments.")
if memory < 7.5:
    print(f"VRAM {memory:.1f} GB is under homr's 8 GB floor: keep SHEET2PLAY_BATCH=4 or lower.")
elif memory < 12:
    print(f"VRAM {memory:.1f} GB: SHEET2PLAY_BATCH=6 is a reasonable starting point.")
PY

log "Ready"
cat <<'EOF'
Next steps, in order:

  1. Datasets. Only mxl.tar.gz (1.9 GB) and PDMX.csv are needed from PDMX's 14.4 GB -
     homr renders its own images, so pdf.tar.gz is not required.
     Put them under vendor/homr/datasets/pdmx/ and keep everything on the LINUX
     filesystem, never /mnt/c - cross-filesystem I/O is the likeliest cause of the
     70 s/iteration case reported in upstream issue #61.

  2. Smoke test, and watch seconds/iteration in the first 15 minutes:
         cd vendor/homr && python3 -c "from training.transformer.train import train_transformer; train_transformer(smoke_test=True)"
     Under ~5 s/it, proceed. Over ~10 s/it, stop - renting is cheaper than waiting.
     Note the progress bar covers the WHOLE run, not one epoch.

  3. Fine-tune:
         SHEET2PLAY_BATCH=4 python3 -c "from training.transformer.train import train_transformer; train_transformer(fine_tune=True)"
EOF
