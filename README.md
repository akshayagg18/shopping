# Shopping Sessions — Performance V2

Optimized C++20 submission candidate for [Builders Buildathon 2026 — Databricks Shopping Sessions](https://www.joinbuilders.org/buildathon/tracks/shopping-sessions).

**Status:** Tested locally; official development fixtures, Docker runtime and competition score have NOT been verified for this commit. **The goal is under 5 seconds, but this has not yet been proven.** See [Performance and validation report](docs/PERFORMANCE_V2.md).

## What's different from the earlier 31-second entry?

Parallel memory-mapped CSV ingestion, hash-partitioned deduplication, safe approximate duplicate detection followed by exact resolution, cached user root mapping, linear-time per-person bucketing, local sorting, and no raw-event binary scratch-file round trip. Existing campaign-assistance interval compression and dense aggregates remain.

The approximate duplicate filter is a *routing accelerator only*: it never removes an ID or conflates IDs on a hash collision; all potential duplicates are compared by full ID and earliest ingest time.

## Submission

At the repository root there is a `Dockerfile`. The competition builds it and runs its entrypoint against the mounted `/data` folder. The entrypoint writes the two exact Parquet datasets into `/output/user_daily/` and `/output/campaign_daily/`.

Submit `https://github.com/akshayagg18/shopping` with the **40-character commit hash for the performance-v2 branch**. Do not assume the default branch `main` is this implementation.

## Local checks

```bash
python3 -m pytest -q tests/
g++ -std=c++20 -O3 -DNDEBUG -pthread src/solver.cpp -o shopping_core
./shopping_core /path/to/data /path/to/output /path/to/scratch
```

The C++ core writes temporary intermediate summary CSV files. At scoring time, `src/export_parquet.py` invokes the core and converts these summaries into Parquet via DuckDB.

**Mandatory before relying on the score:** Obtain `generator.zip` and `dev-answer.zip` from the official track page and execute:

```bash
bash scripts/verify_docker.sh /absolute/path/to/generated-dev-data /absolute/path/to/unzipped-dev-answer
```

The local environment used to author this implementation could not fetch the official ZIPs or run Docker. A passing local test suite is not equivalent to official correctness, nor does a fast C++ core prove a fast complete container.

## Layout

- `src/solver.cpp` — complete C++ cleaning, DSU, sessionization and attribution engine.
- `src/export_parquet.py` — final Parquet export, using DuckDB.
- `tests/` — targeted and randomized correctness tests.
- `scripts/` — official Docker comparison helpers.
- `docs/PERFORMANCE_V2.md` — detailed benchmark and limitations.

The event deduplication phase preserves the earliest *ingested* structurally valid CSV row for each event ID, then applies event validation, including invalid-first-copy precedence. Unknown product categories, byte-exact IDs, linked identities, 30-minute gap rule, seven-day click attribution, deterministic tie breaks and organic credit are implemented according to the official published rules.
