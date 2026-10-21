#!/usr/bin/env bash
# Phase 3 checks of the shipped reader, each under the supervisor, one at a time: parity with the
# frozen research reader, then peak memory on each PDF given (the library's densest; their names
# stay out of the repository).
#
#   bash run-checks.sh TAG PDF...
R="C:/Users/bur4x/Desktop/lecture/big_projects/Sheet2Play/Research/omr"
P="C:/Users/bur4x/Desktop/lecture/big_projects/Sheet2Play/Bridge/.venv-homr-gpu/Scripts/python.exe"
O="$R/reports/song-tempo/phase3"
tag="${1:-1}"
shift
cd "$R"
.venv/Scripts/python.exe -B guarded_execution.py --output "$O/jobs/parity-$tag" --max-seconds 3600 -- \
  "$P" -I -B "$R/tempo_marks_parity.py" --output "$O/parity" || { echo "FAILED parity"; exit 1; }
index=0
for pdf in "$@"; do
  index=$((index + 1))
  .venv/Scripts/python.exe -B guarded_execution.py --output "$O/jobs/memory-$index-$tag" --max-seconds 900 -- \
    "$P" -I -B "$R/tempo_marks_memory.py" "$pdf" || { echo "FAILED memory $index"; exit 1; }
done
echo DONE
