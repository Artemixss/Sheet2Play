#!/usr/bin/env bash
# Phase 2 OCR development runs, each under the supervisor, one at a time. Resumable: a rerun
# skips finished items (rows.jsonl) of a run directory that already exists.
R="C:/Users/bur4x/Desktop/lecture/big_projects/Sheet2Play/Research/omr"
P="C:/Users/bur4x/Desktop/lecture/big_projects/Sheet2Play/Bridge/.venv-homr-gpu/Scripts/python.exe"
cd "$R"
tag="${1:-1}"
for split in dev dev-b; do
  for set in truth control; do
    run="reports/song-tempo/phase2/runs/ocr-$split-$set"
    .venv/Scripts/python.exe -B guarded_execution.py --output "reports/song-tempo/phase2/jobs/ocr-$split-$set-$tag" \
      --max-seconds 7200 -- "$P" -I -B "$R/tempo_read.py" read --split "$split" --set "$set" --candidate ocr --run "$R/$run"
    "$P" -I tempo_read.py score --run "$run" > /dev/null
  done
done
echo DONE
