# Shopping Sessions — Builders Buildathon 2026

**Standalone GitHub repository candidate** for **Databricks — Shopping Sessions**.

Challenge: https://www.joinbuilders.org/buildathon/tracks/shopping-sessions

**What you upload to GitHub:** the *contents* of this folder, with `Dockerfile` directly in the repository root. Do **not** upload the ZIP as a single file. The competition's score is the runtime of a fully correct container on hidden datasets; lower is better.

## Status / evidence

- C++20 core compiled successfully with GCC 14, and **9 tests passed** locally (including a six-seed randomized comparison against an independently implemented Python oracle).
- Separate synthetic test: **500,000 events + 50,000 clicks** processed in **0.36–0.45 s** in this development container for the C++ core only; output Parquet conversion and official hardware not measured. This is **NOT** an official score and does not establish scaling to 60M events.
- **NOT YET verified:** the official 36 edge-case fixtures, 1M-event dev-answer comparison, Docker build, DuckDB Parquet conversion, official 20M practice data, and final 60M runtime. The build environment here had no working external package download, Docker daemon, or DuckDB module. See `docs/VALIDATION_STATUS.md`.

**Do not treat the ZIP as officially validated until the Docker run and official dev-answer comparison pass.** The platform itself checks the dev set and returns differing-row counts when incorrect, but a failed attempt consumes time and a submission slot.

## Design

1. **C++20 parser and processing core** (`src/solver.cpp`): strict CSV parsing, F1/F2/F3 timestamp normalization, string-exact deduplication with earliest-ingest precedence, union-find linked identities (byte-wise canonical ID), sessionization, latest-click credit, and assisted campaign counts.
2. **Adaptive attribution:** small groups scan qualifying clicks; larger groups merge campaign-specific seven-day coverage intervals. Avoids materializing giant click × session joins.
3. **Dense campaign/day aggregation**, and one-pass customer session + category totals.
4. **DuckDB export** (`src/export_parquet.py`) writes `/output/user_daily/part-0.parquet` and `/output/campaign_daily/part-0.parquet` with exactly the official column names and `DATE` day types.
5. Large intermediate binary file is written to **`/scratch`**, never `/tmp`, because the official runtime provides only 64 MB of writable tmpfs and mounts its root filesystem read-only.

Official runtime notes, from challenge page: linux/amd64, 8 pinned hyperthread vCPUs, 24 GB memory, no swap, max 50 GB total `/scratch`+`/output`, 3-minute final limit per run, runs as uid 1000, no runtime network. Docker builds have network access for up to 10 minutes.

## To submit (GitHub website, no coding knowledge required)

1. Extract this ZIP on your PC.
2. Create a **new public GitHub repository**, for example `shopping-sessions-buildathon`.
3. Upload **all of the extracted folder's contents** to the *top level* of the repository. In particular, GitHub must display `Dockerfile`, `run.sh`, `src/`, `README.md` at the root. Do not nest everything under another `SHOPPING_SESSIONS_SUBMISSION/` folder.
4. Commit the upload. Note the **commit SHA** (use the current commit displayed on GitHub).
5. Open https://www.joinbuilders.org/buildathon/tracks/shopping-sessions , sign in to your team, and paste the public repository URL **and the commit SHA**, as required by the form.
6. Check whether the submission passes the official 1M-event dev check and then receives a practice runtime. A submitted entry is **not** automatically proof of correctness or a strong final score.

### Strongly recommended: verify before step 5

Download the official `generator.zip`, `dev-answer.zip`, and DuckDB starter from the challenge page. The official dev data uses seed 1 with ~1 million events; follow the generator's included README to generate it. Unpack dev-answer. With Docker installed and running on your local machine, from the repo root:

```bash
bash scripts/verify_docker.sh /absolute/path/to/generated-dev-data /absolute/path/to/unzipped-dev-answer
```

On Windows, run this command in Git Bash or WSL2. The script builds the Docker image, runs it with nearly the same filesystem permissions as official scoring, writes Parquet files locally and compares against the supplied dev answers. Its comparison command assumes dev-answer contains `user_daily.csv` and `campaign_daily.csv`, which the official page says it does.

If the expected-data archive uses a different directory layout, point the script at the directory containing the two CSVs. A successful local comparison is necessary but not sufficient to prove hidden correctness.

## Inspect locally without Docker (C++ core only)

From the repository root on a Linux or WSL2 machine:

```bash
g++ -std=c++20 -O3 -DNDEBUG src/solver.cpp -o shopping_core
./shopping_core /path/to/data /tmp/output /tmp/working
# It writes /tmp/working/user_daily.csv and campaign_daily.csv for inspection.
python3 -m pytest -q tests/
python3 tests/benchmark_synthetic.py --events 500000
```

The Docker entrypoint automatically converts the interim CSVs to **Parquet**; manually running `shopping_core` does not.

## Input and output requirements

Input directory (read-only): `/data/events/*.csv`, `/data/clicks/*.csv`, `/data/links/*.csv`, `products.csv`, `campaigns.csv`, `manifest.json`.

Outputs (direct Parquet files; no extra columns):

- `/output/user_daily/part-0.parquet`: `user_id` VARCHAR, `day` DATE, `sessions` BIGINT, `events` BIGINT, `revenue_cents` BIGINT, `top_category` VARCHAR nullable.
- `/output/campaign_daily/part-0.parquet`: `campaign_id` VARCHAR, `channel` VARCHAR, `day` DATE, `sessions` BIGINT, `purchasing_sessions` BIGINT, `revenue_cents` BIGINT, `assisted_sessions` BIGINT.

Filesystem and environment are read from `DATA_DIR`, `OUTPUT_DIR`, `SCRATCH_DIR`, `NCPU` (with official defaults). `SHOPPING_KEEP_WORK=1` preserves temporary CSVs for debugging, but increases disk usage.

## Known limitations / next steps

- Full correctness **has not been independently verified against the official dev fixtures**. Do not claim 100% accuracy yet.
- Entire core executes on one thread. Larger hardware may support further gains with parallel input parsing/sorting, but that must not break correctness.
- Peak memory and full 60M runtime are not yet measured. Raw events and event IDs are held in RAM for deduplication before being compacted; official runtime has 24 GB available.
- Raw fields are guaranteed by the official generator to contain no commas, quotes or embedded LF/CR, so the interim summary CSVs use ordinary comma separators. If arbitrary tab/control or comma content were introduced outside the published generator guarantees, the intermediary would need escaping changes.
- Package has no data, API keys, or credential files. Do not commit official datasets to the public repository.

See `docs/VALIDATION_STATUS.md` and `docs/ARCHITECTURE.md`.
