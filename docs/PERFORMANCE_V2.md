# Version 2 — Performance and correctness report

## Objective

Reduce the previous practice result of approximately 31 seconds to under 5 seconds on the Buildathon's approximately 20 million event hidden practice dataset. **This goal has NOT been achieved or independently demonstrated as of this commit.**

## Architecture improvements

1. Parallel memory-mapped CSV ingestion (no per-row `std::getline` allocation).
2. Hash-sharded event-ID partitioning instead of a global event-ID comparison sort.
3. Two-stage, two-bitset duplicate candidate filter. This filter cannot cause the program to miss an exact duplicate: a repeated event ID necessarily sets both its filter bits on its second occurrence. False positives proceed to exact deduplication, using full byte-wise IDs and earliest ingest time. The filter never discards an event by itself.
4. Cache canonical DSU roots for user IDs already observed in links/clicks, and preserve these in event records during parallel validation. Register remaining event-only IDs once.
5. Linear-time counting bucketization by person; sort only within a person's events in parallel. No global event person/time comparison sort.
6. Eliminate the binary scratch write/read of all validated events; write only the relatively small daily summaries as CSV for DuckDB Parquet conversion.
7. Preserve tested adaptive attribution (per-session click scan for small groups, merged per-campaign seven-day intervals for larger groups), dense campaign/day stats, and fused per-person session summaries.

## Local timings — not the official scorer

Environment: Linux container, 4-CPU cgroup quota (5 visible logical CPUs), GCC 14, synthetic CSV with 32 event files, 8 click files, 10M event rows and 1M click rows, 333,333 resulting customer-day rows. Includes input read, deduplication, identity mapping, sorting, attribution, and CSV summaries; **excludes Python startup and Parquet conversion**. Run-to-run variation occurs due to shared hardware.

| Implementation | 10M-event C++ core wall time |
| --- | ---: |
| Original v1 C++ core | 12.85 s |
| v2 optimized C++ core | 3.82 s |

Observed ratio: approximately 3.36x. Peak v2 resident memory was around 1.7–1.9 GB on this dataset. Local input generation was separate and is not counted. This generator differs substantially from the organizers' hidden event distributions, user skew, malformed lines and repeated IDs.

## Verified correctness

- **11/11 local Pytest tests passed**, including six randomized differential tests versus an independently implemented Python oracle.
- Output aggregates from v1 and v2 were **identical** on an additional 10M-event synthetic workload: 333,333 `user_daily` rows and 2,001 `campaign_daily` rows.
- Cross-file duplicated IDs, earliest-invalid duplicate precedence, byte-sensitive IDs, links, tie-breaking, attribution windows, and Bloom-filter false positives have targeted tests.

## Not verified

- Official generator fixtures and `dev-answer.zip`: inaccessible in this container.
- Docker build and full runtime, including DuckDB Parquet writer: not runnable in this environment.
- 20M hidden practice score, final 60M speed, and the under-5-second target: NOT yet verified.

## How to reproduce and improve

```bash
python3 -m pytest -q tests/
g++ -std=c++20 -O3 -DNDEBUG -pthread src/solver.cpp -o shopping_core
bash scripts/verify_docker.sh /absolute/path/to/generated-dev-data /absolute/path/to/unzipped-dev-answer
```

For official submission, provide the **exact commit SHA on the `performance-v2` branch** rather than assuming `main` is this implementation. Verify the official correctness gate first, then inspect the reported practice runtime and per-stage logs before further optimization.

## External research

- [Database CPU execution and vectorization](https://www.cs.cmu.edu/~15721-f24/papers/X100_Hyper_Pipelining.pdf)
- [Parallel integer sorting algorithm design](https://github.com/eloj/radix-sorting)
- [DuckDB efficient ingest/API options](https://duckdb.org/docs/current/data/appender)
- [Official Shopping Sessions rules](https://www.joinbuilders.org/buildathon/tracks/shopping-sessions/files/rules.md?inline=1)
