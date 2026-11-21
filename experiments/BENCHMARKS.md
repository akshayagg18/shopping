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

Scale probe: official generator seed 2 with 20,000,000 requested events and 5,000,000 requested clicks. A Windows Docker Desktop run with 8 CPUs, a 24 GB container limit, no network, uid 1000 and a read-only root did not finish within the official five-minute practice ceiling and was stopped. The corrected `POLARS_OOC_SPILL_DIR=/scratch/polars-spill` prevented the earlier read-only-root spill panic, but the run still exceeded the cap. This is a failed local scale gate, not an official score; the Docker VM's effective resources and Windows bind-mount behavior differ from the scorer.

Commands and full validation procedure are in the root README. Official scorer timing remains the only competitive measurement.
