# Architecture and mathematics

## Strict parsing and event precedence

All input CSV lines are handled using the challenge's restricted dialect: comma separators, LF terminator, whole-field double quotes only, and exact untrimmed identifiers. `\r` is retained if it appears before `\n` and makes a last-field timestamp or price invalid. The C++ parser discards malformed lines *before* event/click deduplication. For events, it sorts on the exact event ID (using a 64-bit hash only as a sort prefix, followed by full byte-wise string equality) and earliest ingestion timestamp, then validates only the chosen copy. This prevents a later valid duplicate from rescuing an earlier invalid copy.

## Identity resolution

A union-find DSU processes all link pairs first, including IDs never seen in an event. Each component maintains the **byte-wise minimum** identifier. A valid event or click with an unlinked ID forms a singleton person. All IDs are never trimmed or case-normalized.

## Sessions

Sorted canonical person/event timestamp records feed a single-pass session processor. A new session starts iff consecutive event timestamps differ by >1,800,000 ms. Events sharing a timestamp join the same session. All events' counts and purchase revenue accumulate into the **session-start UTC day**, even across midnight.

Top category is based on purchase revenue summed over all sessions starting that day. Zero purchase means null; ties resolve using raw byte-wise category ordering.

## Credit

The most recent qualifying click with `click.ts <= session_start` and `session_start - click.ts <= 7 days` is credited. When multiple clicks have the same latest timestamp, their IDs are byte-wise sorted and the smallest is picked. No click means `organic` credit.

## Assists — two correct implementations

For small user groups, each session scans the preceding seven-day click range and increments each unique campaign's assistance counter once.

For larger groups, each campaign's timestamped clicks define closed coverage intervals `[click_ts, click_ts + 7days]`. Consecutive overlapping intervals are merged. Every session inside the merged interval is assisted exactly once by that campaign. Sorted session timestamps permit binary-search interval boundaries; grouped per-day index ranges permit aggregating large session spans without enumerating all click-session matches. This is **exact** for the published rule and specifically reduces work from repeated campaigns and whale users.

Runtime path selection uses `sessions_count × clicks_count > 12,000` as a provisional threshold. This was not calibrated against official data.

## Campaign counters

Only known campaigns plus one `organic` have output rows. The program accumulates their credited sessions, purchasing sessions, revenue and assists in a dense array indexed by `(campaign, UTC day)`; rows are emitted only when they have positive credited or assisted session counts. The total credited sessions must equal the number of constructed sessions (runtime assertion).

## Temporary files and memory

Deduplication requires sorting raw event IDs. A compact `Event` binary scratch stream is produced under `/scratch`, raw duplicate records are freed, and the clean events are loaded for person/time sorting. `/scratch` is writable in the official container, while `/tmp` is limited to 64 MB. DuckDB reads aggregated CSV files from `/scratch`, casts exact output columns, and writes final Parquet files under `/output`.
