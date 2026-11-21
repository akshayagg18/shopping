# V2 validation status

**Verified locally:** C++20 GCC compilation with `-pthread`, 11/11 pytest cases including independent randomized oracle, 10M synthetic v1-v2 CSV aggregate equivalence, 10M synthetic core timing (~3.82s v2 versus ~12.85s v1).

**Not verified in this environment:** official generator ZIP, 36 organizer fixtures, 1M dev-answer CSVs, Docker image execution, DuckDB/Parquet conversion, scoring hardware, 20M hidden practice time, final correctness or time.

The sub-five-second goal is a target, not a verified result. Retest and inspect official feedback after submission.
