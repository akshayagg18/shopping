# Shopping Sessions V2 → V3: measured pipeline profiling

Date: 2026-11-21 UTC.

## Scope and limits
- Reused the 10,000,000-event synthetic dataset, approximately 1,000,000 clicks and 657 MiB of input, produced during local development.
- Local environment: four-CPU quota, 5.8 GiB RAM. V2 default is eight worker threads.
- Eight **measured** C++ core runs after one warm-up. Each stage is the elapsed time between cumulative checkpoints in stderr.
- These are not the competition's 13.16-second Docker runtime. They **exclude Python startup and DuckDB Parquet export**.
- Row order is not part of the competition's output contract; a repeated-run sorted-row comparison matched. Campaign output bytes were identical across eight runs.

## Eight-run baseline timing

| Stage | Mean (ms) | Median (ms) | Min–max (ms) | Share |
| --- | ---: | ---: | ---: | ---: |
| Event deduplication and validation | 1756.6 | 1744.5 | 1640–1869 | 48.9% |
| Click parse, deduplication and sorting | 815.0 | 802.5 | 738–910 | 22.7% |
| Event CSV parsing | 355.3 | 351.5 | 278–447 | 9.9% |
| Session aggregation, attribution, CSV writing | 250.6 | 243.0 | 227–325 | 7.0% |
| Customer bucketing and local sorting | 234.6 | 234.0 | 227–243 | 6.5% |
| Canonicalizing validated event IDs | 110.8 | 105.5 | 94–152 | 3.1% |
| Metadata and linked customer IDs | 40.5 | 39.0 | 36–54 | 1.1% |
| Registering event-only customer IDs | 31.6 | 32.0 | 28–34 | 0.9% |
| **Total C++ core** | **3595.0** | **3593.0** | **3411–3792** | **100%** |

Complete C++ process including startup/cleanup: mean **3684.9 ms**, median **3678.1 ms**, sample standard deviation **113.2 ms**.

## Targeted experiment

Event deduplication+validation was nearly half the core runtime. The most successful simple change was to avoid the repeated pointer-heavy `std::unordered_map` lookups for canonical customer identity in the validation loop. V3 adds a **compact, read-only open-addressed ID→person lookup table**, initialized after processing links and clicks. Each lookup compares full original strings; hash collisions do not affect correctness. The old dictionary remains for the rest of the pipeline.

Three interleaved paired comparison rounds, same input:

| Version | C++ process wall mean (ms) | Dedup/validation mean (ms) |
| --- | ---: | ---: |
| V2 baseline | 4250.4 | 2009.7 |
| V3 flat customer-ID lookup | **3446.5** | **1499.3** |
| V3 flat lookup + alternate two-pass Bloom | 3497.9 | 1492.0 |
| V2 + direct full-ID hash-table dedup (separate 3-run experiment) | 3814.0 | 1915.0 |

The selected flat-lookup-only implementation improved full C++ wall time by **18.9%** and deduplication/validation by **25.4%** in the paired experiment. The two-pass variant was not selected because it was slightly slower overall despite comparable dedup time.

## Correctness and next steps

- V3: **11 of 11 local tests passed**, including randomized comparisons with an independent Python oracle.
- V3 customer and campaign daily CSV aggregates matched V2 on the full 10M-event synthetic dataset after sorting rows.
- Two additional measured V3 runs using the profiler: 3292.5 ms mean process wall time, identical sorted outputs.
- Not yet run: the official development-answer fixture comparison, complete Docker and DuckDB Parquet output validation, or official hidden practice scoring.
- Next candidate: click ingestion / deduplication / two global click sorts (22.7% of V2 local core time). Profile with the real organizer data before promising any absolute score.

**Do not claim the 5-second official target is achieved based on local C++ core timings.**
