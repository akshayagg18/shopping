# Builders Buildathon 2026 — Shopping Sessions

Exact, performance-oriented solution for the Databricks Shopping Sessions track. The pipeline reads dirty CSV shards from `/data` and writes the two required Parquet datasets to `/output/user_daily/` and `/output/campaign_daily/`.

## Architecture

- Spec-exact physical-line CSV validation; malformed rows are rejected before field interpretation.
- Polars lazy scans, hash deduplication, identity joins, session sorting and aggregations.
- Path-compressed union-find for transitive identity resolution.
- Linear sliding-window click sweep per person for last-click credit and unique-campaign assists, avoiding a session×click range join.
- One narrow materialization after sessionization feeds both output aggregates, avoiding a second full event scan and sort.

## Build and run

```bash
docker build -t shopping-sessions .
mkdir -p out scratch
docker run --rm --network none --read-only --user 1000:1000 \
  --cpus 8 --memory 24g --tmpfs /tmp:rw,size=64m \
  -e DATA_DIR=/data -e OUTPUT_DIR=/output -e SCRATCH_DIR=/scratch \
  -e HOME=/scratch -e NCPU=8 -e MEM_GB=24 \
  -v "$PWD/dev:/data:ro" -v "$PWD/out:/output" -v "$PWD/scratch:/scratch" \
  shopping-sessions
```

For a direct local run:

```bash
python -m pip install -r requirements.txt
DATA_DIR=dev OUTPUT_DIR=out NCPU=8 python src/pipeline.py
```

## Official verification

Download `rules.md`, `starter-polars.zip`, `generator.zip`, and `dev-answer.zip` from the official track page. Then:

```bash
python starter-polars/scripts/run_fixtures.py starter-polars/fixtures -- python src/pipeline.py
generate --seed 1 --events 1000000 --clicks 250000 --output dev
DATA_DIR=dev OUTPUT_DIR=out NCPU=8 python src/pipeline.py
python starter-polars/scripts/compare.py out dev-answer
```

Verified results for this revision:

- 36/36 official edge fixtures pass.
- Both 1M dev tables exactly match the official answers (117,038 `user_daily` rows; 27,400 `campaign_daily` rows).
- Local Python median: 2.958 seconds over three warm runs.
- Scorer-like Docker wall time on Windows Docker Desktop: 9.154 seconds. This is not comparable to the official Linux scorer.

## Repository layout

- `src/pipeline.py` — implementation
- `tests/` — unit tests and verification notes
- `experiments/` — benchmark notes (generated data is ignored)
- `submission/` — scorer packaging and submission checklist
- `research.md` — rules, competition and optimization research
- `FIRST_SUBMISSION_REPORT.md` — first-submission status and recommendations

The implementation uses Polars 2.1.0 under its MIT license. Challenge starter materials and generated data are intentionally not committed. This repository is MIT licensed.
