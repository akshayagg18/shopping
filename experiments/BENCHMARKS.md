# Benchmarks

Dataset: official generator seed 1, 1,000,000 requested events and 250,000 requested clicks. Machine: local Windows host; 8 Polars threads. Generated data and outputs are ignored by Git.

| Variant | Seconds | Notes |
| --- | ---: | --- |
| Recompute event plan for top-category path | 4.797 | Exact dev match |
| Narrow event materialization shared by both aggregates | 2.920 | Run 1 |
| Same | 2.998 | Run 2 |
| Same | 2.958 | Run 3 |
| Same, median | **2.958** | 38.3% faster than 4.797 s |
| Docker image with scorer-like flags | 9.154 | Windows Docker Desktop overhead; exact match |

Commands and full validation procedure are in the root README. Official scorer timing remains the only competitive measurement.
