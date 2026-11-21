#!/bin/sh
set -eu
: "${DATA_DIR:=/data}" "${OUTPUT_DIR:=/output}" "${SCRATCH_DIR:=/scratch}"
export DATA_DIR OUTPUT_DIR SCRATCH_DIR
mkdir -p "$SCRATCH_DIR/polars-spill"
export TMPDIR="$SCRATCH_DIR" HOME="$SCRATCH_DIR" POLARS_TEMP_DIR="$SCRATCH_DIR"
export POLARS_OOC_SPILL_DIR="$SCRATCH_DIR/polars-spill"
exec python3 /app/src/pipeline.py
