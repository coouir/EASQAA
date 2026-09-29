#!/usr/bin/env bash
# Detector training wrapper (SPEC §4.3). Start it inside tmux with nohup, e.g.
#   tmux new-session -d -s m1_train 'nohup bash scripts/train_detector.sh >/dev/null 2>&1'
# Training resumes from <OUT>/last.pt, so re-running the same command continues an interrupted run.
# A crashed process is restarted up to 3 times (each restart resumes from the last finished epoch).
set -u
cd "$(dirname "$0")/.."
PY=${PY:-/home/cvlab/anaconda3/envs/easqaa/bin/python}
OUT=${OUT:-outputs/detector}
mkdir -p "$OUT"
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
for attempt in 1 2 3; do
  echo "[$(date -Is)] attempt $attempt (commit $(git rev-parse --short HEAD))" >> "$OUT/nohup.log"
  "$PY" -m sarqa.detector.train --out "$OUT" "$@" >> "$OUT/nohup.log" 2>&1
  rc=$?
  echo "[$(date -Is)] exit code $rc" >> "$OUT/nohup.log"
  if [ "$rc" -eq 0 ]; then exit 0; fi
  sleep 30
done
exit 1
