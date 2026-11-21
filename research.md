# Shopping Sessions research

Research timestamp: 2026-11-21 (Asia/Singapore). Confirmed facts are separated from implementation hypotheses.

## Confirmed: Buildathon rules and scoring

- The event runs November 20–22, 2026. Kickoff is Nov 20 at 6:00 PM ET; submissions close Nov 22 at 11:00 AM ET; the closing ceremony starts at noon ET. Source: https://www.joinbuilders.org/buildathon
- Entrants must be current students using a school email. Teams have one or two people, may compete remotely, and can enter multiple tracks. AI and other tools are permitted unless a track says otherwise. Source: https://www.joinbuilders.org/buildathon
- Code must be MIT licensed. Pre-existing code and open-source dependencies are allowed when disclosed in the README. Source: https://www.joinbuilders.org/buildathon
- Shopping Sessions accepts a public GitHub repository with a root Dockerfile and an optional commit SHA. The repository must be at most 50 MB and contain no dataset. Source: https://www.joinbuilders.org/buildathon/tracks/shopping-sessions
- Practice data contains about 20M events. Each team receives two submissions per hour; one queued submission at a time; rejected submissions consume quota but do not replace the best score. Lower container run time wins and equal scores favor the earlier submission. Source: track page and https://www.joinbuilders.org/buildathon
- Every submission first runs against the public 1M-event dev set with a three-minute cap. A dev mismatch returns differing rows and logs. Hidden practice feedback withholds values/logs and reports only exit state, memory exhaustion, and counts of missing/extra/differing rows. Source: track page.
- Practice is timed once, or three times with median scoring when the first run is below 20 seconds. Practice runs are capped at twice the baseline and never above five minutes. Runtime includes container startup, engine startup, CSV reads, output writes and exit. Source: track page.
- The final rebuilds the selected commit and runs it three times on about 60M newly generated events, each capped at three minutes. Any over-limit run produces no final score. At least the five fastest entries are retimed five times alone on one idle machine. Source: track page.
- Scorer resources: linux/amd64, image at most 8 GB, 8 pinned Intel Xeon hyperthreads (Cascade Lake or newer, AVX-512), 24 GB RAM, no swap, no runtime network, read-only root, uid 1000, writable `/output` and `/scratch`, and a 64 MB `/tmp`. Source: official Polars starter README and track page.
- The practice baseline is PySpark local mode at 171.91 seconds, scorer version `shopping-sessions-4`. Source: track page viewed 2026-11-21.
- The leaderboard had 58 Shopping Sessions teams when last checked. The visible best score was 1.24 seconds (`last friday night`); other displayed leading scores were 1.46–1.58 seconds. Times can vary by about 20% across machines. Source: https://www.joinbuilders.org/buildathon/leaderboard viewed 2026-11-21.
- Organizer announcements and chat are embedded on the leaderboard. No indexed public GitHub implementation or discussion specific to this just-opened track was found in focused web/GitHub searches; generic clickstream repositories do not define this benchmark's semantics. Sources: leaderboard and focused GitHub/web searches on 2026-11-21.

## Confirmed: official artifacts

- Rules: https://www.joinbuilders.org/buildathon/tracks/shopping-sessions/files/rules.md
- Polars starter: https://www.joinbuilders.org/buildathon/tracks/shopping-sessions/files/starter-polars.zip
- DuckDB starter: https://www.joinbuilders.org/buildathon/tracks/shopping-sessions/files/starter-duckdb.zip
- PySpark starter: https://www.joinbuilders.org/buildathon/tracks/shopping-sessions/files/starter-pyspark.zip
- Generator: https://www.joinbuilders.org/buildathon/tracks/shopping-sessions/files/generator.zip
- Development answers: https://www.joinbuilders.org/buildathon/tracks/shopping-sessions/files/dev-answer.zip

All three starters are intentionally empty end-to-end skeletons. DuckDB is compact but warns that its CSV reader may repair malformed rows and treats quoted empties differently. PySpark explicitly recommends reading physical lines because its CSV reader treats `\r` as a line ending. Polars provides low startup overhead and fast local vectorized processing but also requires custom line validation. PySpark's 171.91-second baseline makes it unsuitable for a first competitive runtime; Polars was selected for implementation speed plus adequate performance.

The official starter includes 36 hand-authored fixtures: 20 event/session cases, 12 attribution cases and 4 linked-identity cases. The public dev corpus is generated with `--seed 1 --events 1000000 --clicks 250000`.

## Confirmed: exact data semantics

### CSV and validation order

- Input shards are all `*.csv` files in `events/`, `clicks/` and `links/`; file counts and sizes vary and header-only files occur.
- Only `\n` terminates a record. `\r` is data. Fields may be wholly quoted; no valid value contains comma, quote or newline. Wrong field counts, partial/unbalanced quoting and empty lines are malformed.
- Empty fields are null. Whitespace, case and quoting-normalized contents otherwise compare exactly. “Digits” means ASCII `0`–`9`.
- Events are parsed, empty `event_id` rows removed, deduplicated by earliest valid F1 `ingest_ts`, then validated. A later valid duplicate cannot rescue an earlier invalid kept copy.
- Clicks are parsed, empty `click_id` rows removed, deduplicated (copies are identical), then validated.

### Timestamps and windows

- Valid event/click timestamps are F1 UTC seconds, F2 seconds with a strict `±HH:MM` offset, or ASCII epoch milliseconds. Fractional ISO seconds, lowercase separators/zones, leap seconds, impossible dates and malformed offsets are invalid.
- Events require `window_start <= ts < window_end`. Clicks require `window_start - 7 days <= ts < window_end`.
- Events with `ingest_ts - ts > 24h` are dropped; exactly 24h and negative latency are retained.
- A discovered engine pitfall: Polars/Chrono accepts `second=60` by normalizing it to the next minute. The implementation therefore validates hour/minute/second ranges in regex before parsing. This error caused exactly 300 extra dev events before correction.

### Identity, sessions and outputs

- Nonempty valid link rows define undirected transitive components. Each component's person name is the byte-wise smallest ID, including linked IDs unused by any event or click. Unlinked IDs map to themselves.
- Surviving events for the entire component are ordered by timestamp. A new session begins only when the gap from the prior event exceeds 1,800,000 ms. Equal timestamps never split. The UTC date of the session's first event owns every event in that session.
- Product IDs absent from the clean catalog use category `unknown`. Purchase prices must be 1–10,000,000 ASCII-digit cents; price is ignored for views/carts.
- Session credit uses the latest valid click for that person at or before session start and no more than seven days old; equal-time ties choose byte-wise smallest `click_id`. With none, credit is `organic`.
- Every distinct qualifying non-organic campaign assists the session once, including the credited campaign. A campaign with assists but no credit still receives a daily row.
- Output folders contain one or more direct `*.parquet` children. Integer widths are flexible, strings may use accepted Parquet encodings, but `day` must be Parquet DATE and schemas/values must be exact.

## Confirmed: generator distribution and likely hot operations

The official generator creates roughly one person per 30 events, 1–8 ordinary aliases, rare 50–400-ID chains, several whale people, and shared-device components joining thousands of people. It uses 24–160 event shards, 8–48 click shards and 4–24 link shards. Event duplicates are 2–4%; click duplicates 1–3%; malformed rows 0.05%; about 3% of events are purchases; roughly 60% of sessions have qualifying clicks.

The dominant work is expected to be:

1. Reading and validating tens of millions of variable-form strings.
2. Event deduplication and the global `(person, ts)` sort required by sessionization.
3. Attribution if expressed as an exploding person join or interval join.
4. Repeated materialization/scans if user and campaign outputs are built independently.

## Implemented optimization and measured evidence

- Custom narrow-dialect parsing validates records as physical lines without general CSV repair behavior.
- Union-find makes identity resolution near-linear and handles long chains/shared-device components exactly.
- Attribution is a per-person sliding deque plus campaign counter: `O(clicks + sessions + emitted campaign assists)`, without an all-pairs range join.
- The post-session event frame is narrowed and materialized once. Reusing it for session and top-category aggregation reduced the 1M local run from 4.797 seconds to a 2.958-second median (38.3% faster) while preserving the official exact match.
- Uncompressed Parquet avoids compression CPU and is accepted by the checker.

## Hypotheses and next experiments

- **Likely:** For 20M/60M, Python union-find and attribution loops may become the main limit after Polars sorting. Porting those two components plus raw parsing to a small Rust binary could approach the 1–2 second leaderboard class only if the leaderboard dataset is heavily cached or scores reflect specialized compiled pipelines.
- **Likely:** String interning/categorical encoding of `person`, `campaign_id`, `event_type` and `category` before the session sort could reduce memory bandwidth, but must be benchmarked because encode/decode overhead may erase gains.
- **Hypothesis:** A single compiled radix sort keyed by interned person and integer timestamp, followed by fused session/user/campaign aggregation, can eliminate most intermediate DataFrames and allocations.
- **Hypothesis:** CRLF pre-detection doubles sequential reads in worst-case inputs. The official generator never emits `\r`, so a future competition-only fast path could skip that scan, but doing so would weaken correctness for permitted hand-written inputs and was not adopted.
