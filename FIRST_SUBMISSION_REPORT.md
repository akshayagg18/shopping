# Shopping Sessions — Version 2 candidate report

This is a **new submission candidate**, not evidence of a second official submission.

- Prior reported official practice result: approximately 31 seconds (reported by team).
- New version: optimized C++20 pipeline, plus existing DuckDB Parquet export.
- Local 10M synthetic C++ core: 3.82 seconds (v1: 12.85 seconds, same dataset).
- Local tests: 11/11 passed; v1/v2 aggregate parity on 10M generated events.
- **Unverified**: official dev answers, Docker/Parquet integration, 20M hidden practice runtime and under-five-second target.
- Detailed evidence: `docs/PERFORMANCE_V2.md`.

Do not assume this version wins or meets the official target until the platform reports a correct scored run.
