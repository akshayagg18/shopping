# Validation status

## Completed in the authoring environment

- C++20 source compiled with GCC 14 at -O3.
- Pytest: **9 passed**. Tests include published-rule edge cases, non-overlapping seven-day campaign intervals, byte-wise category ties, dedup-before-validation, offset/epoch timestamps, linked unused IDs, midnight crossing, 30-min boundaries, and six randomized dataset comparisons with an independently implemented Python oracle.
- Synthetic performance smoke test: **500k events / 50k clicks**, core only **0.36–0.45 s** (one development container execution); synthetic generation 1.964 s not included. Not an official or comparable contest benchmark.

## Not completed — do these before confident submission

- Official 36 edge-case fixtures: starter download not available in authoring environment.
- Official `dev-answer.zip` seed-1 1M-event equivalence test: archive inaccessible here.
- Docker image build and runtime test: Docker daemon inaccessible here.
- DuckDB dependency install and final Parquet writer test: external package download blocked.
- Practice 20M events performance and memory test: not executed.
- Final 60M hidden events time/memory/correctness: cannot be verified before official scoring.

**The exact official scoring result is unknown.** This is a substantive working candidate, not a promised winning submission.

## Failing submissions

The official site states that every submission runs a development check first; when wrong, it reports differing rows and logs, rather than scoring a practice runtime. Use such diagnostics to correct the implementation; do not attempt to reverse engineer hidden evaluation data.

## Potential performance optimizations AFTER correctness

1. Profile input parse, event-ID sorting/dedup, event time sorting, session aggregation and Parquet serialization.
2. If sorting dominates, implement a safely tested parallel sort on 8 CPUs.
3. If output conversion dominates, experiment with faster Parquet encoding and more selective threading.
4. Calibrate the small-group/interval-union cutoff on the official generator across multiple seeds, avoiding overfit to one dataset.
