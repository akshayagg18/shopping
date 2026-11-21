# First submission report

**Status:** Candidate created; **NOT submitted**. No GitHub repo or official submission receipt exists yet.

## Implementation

- Compiled C++20 core for strict record parsing and exact aggregation.
- Adaptive small-group scan / campaign-interval-union assistance computation.
- Dense per-campaign/day counters and fused per-person session/user-day accumulation.
- DuckDB Parquet writer in a two-stage Docker image.

## Validation done

- 9 local tests passed, including six independently computed randomized datasets.
- 500k-event synthetic smoke-test core runtime: 0.36–0.45 seconds in authoring container (not official hardware; excludes Parquet conversion).

## Unverified blockers

The official 36 cases, official 1M dev answer, complete Docker build/Parquet export, and 20M practice scoring were not accessible in this environment. The candidate is not proof of a valid submission or of final speed.

## To populate after the user submits

- **GitHub URL:**
- **Exact commit SHA:**
- **Official submission receipt:**
- **Official dev correctness:**
- **Practice runtime (seconds):**
- **Leaderboard rank:**
- **Differing/missing/extra rows if rejected:**

## Highest-value follow-up

Run `scripts/verify_docker.sh` with the official dev corpus and expected output, fix any mismatch, then submit the GitHub commit and inspect official feedback.
