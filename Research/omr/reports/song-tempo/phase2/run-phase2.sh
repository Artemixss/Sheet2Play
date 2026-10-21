#!/usr/bin/env bash
# Phase 2 reads for the freeze ("dev": dev and dev-b) or the one test scoring ("test": test and
# test-b), both candidates, truth and control sets, each under the supervisor, one at a time.
# Resumable: a rerun skips finished items (rows.jsonl) of a run directory that already exists.
R="C:/Users/bur4x/Desktop/lecture/big_projects/Sheet2Play/Research/omr"
P="C:/Users/bur4x/Desktop/lecture/big_projects/Sheet2Play/Bridge/.venv-homr-gpu/Scripts/python.exe"
cd "$R"
mode="$1"
tag="${2:-1}"
case "$mode" in
  dev) splits="dev dev-b" ;;
  test) splits="test test-b" ;;
  *) echo "usage: run-phase2.sh dev|test [tag]"; exit 2 ;;
esac
for candidate in text ocr; do
  for split in $splits; do
    for set in truth control; do
      name="$candidate-$split-$set"
      run="reports/song-tempo/phase2/runs/$mode/$name"
      .venv/Scripts/python.exe -B guarded_execution.py --output "reports/song-tempo/phase2/jobs/$mode-$name-$tag" \
        --max-seconds 7200 -- "$P" -I -B "$R/tempo_read.py" read --split "$split" --set "$set" --candidate "$candidate" --run "$R/$run" \
        || { echo "FAILED $name"; exit 1; }
      "$P" -I tempo_read.py score --run "$run" > /dev/null
    done
  done
done
echo DONE
