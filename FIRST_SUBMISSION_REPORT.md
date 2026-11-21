# First submission report

Date: 2026-11-21 (Asia/Singapore)

## Outcome

A complete first-submission candidate is implemented and containerized.

- Official edge fixtures: **36/36 passed**.
- Official 1M dev answer: **exact match** for both tables.
- Dev output sizes: 117,038 user-day rows and 27,400 campaign-day rows.
- Unit tests: passed.
- Docker: linux/amd64 image builds successfully; 443,198,577 bytes, well below the 8 GB image limit.
- Docker execution was verified on the 1M dev set under no-network, read-only-root, uid 1000, 8 CPU and 24 GB limits.
- A generated 20M-event/5M-click Windows Docker run exceeded the five-minute practice ceiling and was stopped. This local scale gate therefore failed; no competitive-runtime claim is made.

## Runtime

| Configuration | 1M dev wall time | Correctness |
| --- | ---: | --- |
| Local Python/Polars before narrow-frame reuse | 4.797 s | exact |
| Local Python/Polars after optimization, 3-run median | 2.958 s | exact |
| Windows Docker Desktop, scorer-like flags | 9.154 s | exact |
| Windows Docker Desktop, generated 20M/5M corpus | >300 s (stopped) | did not finish inside practice cap |

Local and Windows Docker results are not comparable to the official Linux scorer. The optimization reduced the local run by 38.3% by avoiding a second event scan, deduplication, identity join and session sort.

The first scale attempt also exposed a container-specific correctness issue: Polars 2.1's out-of-core engine uses `POLARS_OOC_SPILL_DIR`, not the generic `POLARS_TEMP_DIR`. Without the dedicated setting it tried `/var/tmp` and failed against the read-only root. `run.sh` now creates `/scratch/polars-spill` and exports the dedicated variable. A repeat passed that failure point, but still exceeded the local five-minute ceiling.

## Submission status

No official score was obtained. The GitHub CLI's stored token for the local account is invalid, and the browser reached GitHub's sign-in page rather than an authenticated repository-creation page. The Buildathon page also requires sign-in. Creating/pushing the public repository and entering its commit therefore require the user's authenticated session.

Prepared repository name: `builders-shopping-sessions`.

After GitHub sign-in:

1. Create a public, empty repository named `builders-shopping-sessions` (do not add a README, license or `.gitignore`; they already exist locally).
2. In this directory, add the remote and push `main`.
3. Open https://www.joinbuilders.org/buildathon/tracks/shopping-sessions and sign in.
4. Submit the public repository URL and the commit SHA recorded in `submission/SUBMISSION.md`.
5. Record the practice runtime, rank, correctness status and feedback below.

## Official feedback

- Submission: not sent (authentication blocker)
- Score: not available
- Rank: not available
- Feedback: not available

## Recommendation

Submit this correctness-first Polars revision once authenticated to obtain the only authoritative Linux/24 GB runtime, but treat it as a baseline rather than a competitive candidate: the local 20M scale gate failed. Preserve this exact version, then prioritize a fused compiled implementation (raw parsing, identity encoding, sessionization and attribution) if the official practice run also approaches the cap.
