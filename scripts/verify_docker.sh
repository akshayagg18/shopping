#!/usr/bin/env bash
set -euo pipefail
# Use a directory containing the OFFICIAL generated 1M-event dev corpus.
if [ "$#" -lt 1 ]; then
  echo "Usage: bash scripts/verify_docker.sh /absolute/path/to/dev-data [expected-dev-answer-folder]" >&2
  exit 2
fi
INPUT_DIR="$(cd "$1" && pwd)"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/local-output" "$ROOT/local-scratch"
# For a test-only local bind mount, ensure uid 1000 inside the container can write.
chmod 777 "$ROOT/local-output" "$ROOT/local-scratch"
docker build --platform linux/amd64 -t shopping-sessions-candidate "$ROOT"
docker run --rm --platform linux/amd64 --network none --read-only --user 1000:1000 \
  --tmpfs /tmp:rw,size=64m \
  -e DATA_DIR=/data -e OUTPUT_DIR=/output -e SCRATCH_DIR=/scratch -e HOME=/scratch -e NCPU=8 -e MEM_GB=24 \
  -v "$INPUT_DIR":/data:ro -v "$ROOT/local-output":/output \
  -v "$ROOT/local-scratch":/scratch shopping-sessions-candidate
if [ "$#" -ge 2 ]; then
  python3 -m pip install duckdb==1.4.2
  python3 "$ROOT/scripts/compare_parquet.py" "$2" "$ROOT/local-output"
fi
