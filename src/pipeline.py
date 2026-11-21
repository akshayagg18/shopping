#!/usr/bin/env python3
"""Exact Shopping Sessions pipeline.

Polars performs the wide scans, sorting and aggregation. Two deliberately
small Python components handle the operations that are awkward in a dataframe:
union-find for linked identities and a linear sliding-window attribution sweep.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from datetime import datetime
from itertools import groupby
from operator import itemgetter
import glob
import json
import mmap
import os
from pathlib import Path
from typing import Iterable, Iterator

NCPU = os.environ.get("NCPU")
if NCPU:
    os.environ.setdefault("POLARS_MAX_THREADS", NCPU)

import polars as pl  # noqa: E402


DATA = Path(os.environ.get("DATA_DIR", "/data"))
OUT = Path(os.environ.get("OUTPUT_DIR", "/output"))
SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000
DAY_MS = 24 * 60 * 60 * 1000
SESSION_GAP_MS = 30 * 60 * 1000

ASCII_INT = r"^[0-9]+$"
ISO_TS = (
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"
    r"(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])$"
)

USER_SCHEMA = {
    "user_id": pl.String,
    "day": pl.Date,
    "sessions": pl.Int64,
    "events": pl.Int64,
    "revenue_cents": pl.Int64,
    "top_category": pl.String,
}
CAMPAIGN_SCHEMA = {
    "campaign_id": pl.String,
    "channel": pl.String,
    "day": pl.Date,
    "sessions": pl.Int64,
    "purchasing_sessions": pl.Int64,
    "revenue_cents": pl.Int64,
    "assisted_sessions": pl.Int64,
}


def epoch_ms(value: str) -> int:
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def parse_fields(raw: bytes, count: int) -> tuple[str, ...] | None:
    """Parse one physical line using the challenge's intentionally narrow CSV dialect."""
    parts = raw.split(b",")
    if len(parts) != count:
        return None
    parsed: list[str] = []
    for part in parts:
        if b'"' in part:
            if len(part) < 2 or part[:1] != b'"' or part[-1:] != b'"' or b'"' in part[1:-1]:
                return None
            part = part[1:-1]
        try:
            parsed.append(part.decode("utf-8"))
        except UnicodeDecodeError:
            return None
    return tuple(parsed)


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, value: str) -> str:
        parent = self.parent
        if value not in parent:
            parent[value] = value
            return value
        root = value
        while parent[root] != root:
            root = parent[root]
        while parent[value] != value:
            nxt = parent[value]
            parent[value] = root
            value = nxt
        return root

    def union(self, left: str, right: str) -> None:
        a, b = self.find(left), self.find(right)
        if a != b:
            self.parent[b] = a

    def mapping(self) -> pl.DataFrame:
        minima: dict[str, str] = {}
        for value in self.parent:
            root = self.find(value)
            current = minima.get(root)
            if current is None or value < current:
                minima[root] = value
        rows = [(value, minima[self.find(value)]) for value in self.parent]
        schema = {"raw_user_id": pl.String, "canonical_user_id": pl.String}
        return pl.DataFrame(rows, schema=schema, orient="row") if rows else pl.DataFrame(schema=schema)


def load_identities() -> pl.LazyFrame:
    uf = UnionFind()
    for filename in sorted(glob.glob(str(DATA / "links" / "*.csv"))):
        with open(filename, "rb") as handle:
            for index, raw in enumerate(handle.read().split(b"\n")):
                if index == 0:
                    continue
                fields = parse_fields(raw, 2)
                if fields is not None and fields[0] != "" and fields[1] != "":
                    uf.union(fields[0], fields[1])
    return uf.mapping().lazy()


def contains_crlf(path: str) -> bool:
    """Polars consumes CR in CRLF; route only such files through the exact parser."""
    if os.path.getsize(path) == 0:
        return False
    with open(path, "rb") as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as data:
        return data.find(b"\r\n") >= 0


def python_file_frame(path: str, names: list[str]) -> pl.LazyFrame:
    rows: list[tuple[str, ...]] = []
    with open(path, "rb") as handle:
        for index, raw in enumerate(handle.read().split(b"\n")):
            if index == 0:
                continue
            fields = parse_fields(raw, len(names))
            if fields is not None:
                rows.append(fields)
    schema = {name: pl.String for name in names}
    return pl.DataFrame(rows, schema=schema, orient="row").lazy()


def polars_file_frame(path: str, names: list[str]) -> pl.LazyFrame:
    field = r'(?:"[^"\n]*"|[^",\n]*)'
    pattern = "^" + ",".join(f"({field})" for _ in names) + "$"
    line = pl.scan_csv(
        path,
        separator="\x1f",
        has_header=False,
        skip_rows=1,
        quote_char=None,
        new_columns=["line"],
        schema_overrides={"line": pl.String},
        infer_schema_length=0,
        truncate_ragged_lines=True,
    ).filter(pl.col("line").str.contains(pattern))
    groups = pl.col("line").str.extract_groups(pattern)
    return line.select(
        groups.struct.field(str(index + 1)).str.replace(r'^"(.*)"$', "$1").alias(name)
        for index, name in enumerate(names)
    )


def scan_exact(folder: str, names: list[str]) -> pl.LazyFrame:
    frames: list[pl.LazyFrame] = []
    for path in sorted(glob.glob(str(DATA / folder / "*.csv"))):
        # Small files include header-only shards and the edge fixtures. Routing
        # them here also avoids Polars' NoDataError after skipping a lone header.
        exact_python = os.path.getsize(path) < 4096 or contains_crlf(path)
        frames.append(python_file_frame(path, names) if exact_python else polars_file_frame(path, names))
    if not frames:
        return pl.DataFrame(schema={name: pl.String for name in names}).lazy()
    return pl.concat(frames, how="vertical")


def timestamp_ms(column: str) -> pl.Expr:
    text = pl.col(column)
    iso = (
        text.str.strptime(pl.Datetime("ms", "UTC"), format="%Y-%m-%dT%H:%M:%S%#z", strict=False)
        .dt.epoch("ms")
    )
    return (
        pl.when(text.str.contains(ASCII_INT))
        .then(text.cast(pl.Int64, strict=False))
        .when(text.str.contains(ISO_TS))
        .then(iso)
        .otherwise(None)
    )


def attach_identity(frame: pl.LazyFrame, identities: pl.LazyFrame) -> pl.LazyFrame:
    return (
        frame.join(identities, left_on="user_id", right_on="raw_user_id", how="left")
        .with_columns(pl.coalesce("canonical_user_id", "user_id").alias("person"))
        .drop("canonical_user_id")
    )


def build_events(
    identities: pl.LazyFrame,
    products: pl.LazyFrame,
    window_start: int,
    window_end: int,
) -> tuple[pl.DataFrame, pl.DataFrame]:
    events = scan_exact(
        "events", ["event_id", "user_id", "ts", "ingest_ts", "event_type", "product_id", "price_cents"]
    )
    events = (
        events.filter(pl.col("event_id") != "")
        .with_columns(
            timestamp_ms("ts").alias("ts_ms"),
            pl.col("ingest_ts")
            .str.strptime(pl.Datetime("ms", "UTC"), format="%Y-%m-%dT%H:%M:%SZ", strict=False)
            .dt.epoch("ms")
            .alias("ingest_ms"),
        )
        .group_by("event_id")
        .agg(pl.all().exclude("event_id").sort_by("ingest_ms").first())
        .with_columns(
            pl.col("price_cents").cast(pl.Int64, strict=False).alias("price_num"),
            pl.col("price_cents").str.contains(ASCII_INT).alias("price_digits"),
        )
        .filter(
            (pl.col("user_id") != "")
            & pl.col("ts_ms").is_not_null()
            & (pl.col("ts_ms") >= window_start)
            & (pl.col("ts_ms") < window_end)
            & pl.col("event_type").is_in(["view", "cart", "purchase"])
            & (pl.col("product_id") != "")
            & (
                (pl.col("event_type") != "purchase")
                | (
                    pl.col("price_digits")
                    & pl.col("price_num").is_between(1, 10_000_000, closed="both")
                )
            )
            & ((pl.col("ingest_ms") - pl.col("ts_ms")) <= DAY_MS)
        )
    )
    events = attach_identity(events, identities)
    events = (
        events.sort(["person", "ts_ms"])
        .with_columns(
            pl.col("ts_ms")
            .diff()
            .over("person")
            .gt(SESSION_GAP_MS)
            .fill_null(True)
            .cast(pl.Int64)
            .cum_sum()
            .over("person")
            .alias("session_no")
        )
        .with_columns(pl.col("ts_ms").min().over(["person", "session_no"]).alias("session_start"))
        .with_columns(
            pl.col("session_start").cast(pl.Datetime("ms", "UTC")).dt.date().alias("day"),
            pl.when(pl.col("event_type") == "purchase")
            .then(pl.col("price_num"))
            .otherwise(0)
            .cast(pl.Int64)
            .alias("event_revenue"),
        )
        .join(products, on="product_id", how="left")
        .with_columns(pl.col("category").fill_null("unknown"))
    )

    # Materialize only the narrow post-sessionization columns once.  Both
    # downstream aggregates consume them; keeping this compact frame avoids a
    # second CSV scan, deduplication, identity join and global session sort.
    events_df = events.select(
        "person", "session_no", "session_start", "day", "event_type", "event_revenue", "category"
    ).collect(engine="streaming")

    sessions = (
        events_df.lazy().group_by(["person", "session_no"])
        .agg(
            pl.col("session_start").first(),
            pl.col("day").first(),
            pl.len().cast(pl.Int64).alias("events"),
            pl.col("event_revenue").sum().cast(pl.Int64).alias("revenue_cents"),
            (pl.col("event_type") == "purchase").any().alias("purchasing"),
        )
        .sort(["person", "session_start"])
        .collect(engine="streaming")
    )

    category_top = (
        events_df.lazy().filter(pl.col("event_type") == "purchase")
        .group_by(["person", "day", "category"])
        .agg(pl.col("event_revenue").sum().alias("category_revenue"))
        .sort(["person", "day", "category_revenue", "category"], descending=[False, False, True, False])
        .unique(subset=["person", "day"], keep="first", maintain_order=True)
        .select("person", "day", pl.col("category").alias("top_category"))
    )
    user_daily = (
        sessions.lazy()
        .group_by(["person", "day"])
        .agg(
            pl.len().cast(pl.Int64).alias("sessions"),
            pl.col("events").sum().cast(pl.Int64),
            pl.col("revenue_cents").sum().cast(pl.Int64),
        )
        .join(category_top, on=["person", "day"], how="left")
        .rename({"person": "user_id"})
        .select(*USER_SCHEMA)
        .sort(["user_id", "day"])
        .collect(engine="streaming")
    )
    return sessions, user_daily


def build_clicks(
    identities: pl.LazyFrame,
    campaigns: pl.LazyFrame,
    window_start: int,
    window_end: int,
) -> pl.DataFrame:
    clicks = scan_exact("clicks", ["click_id", "user_id", "campaign_id", "ts"])
    return (
        clicks.filter(pl.col("click_id") != "")
        .unique(subset=["click_id"], keep="first")
        .with_columns(timestamp_ms("ts").alias("ts_ms"))
        .filter(
            (pl.col("user_id") != "")
            & pl.col("ts_ms").is_not_null()
            & (pl.col("ts_ms") >= window_start - SEVEN_DAYS_MS)
            & (pl.col("ts_ms") < window_end)
        )
        .join(campaigns, on="campaign_id", how="inner")
        .pipe(attach_identity, identities)
        .select("person", "ts_ms", "click_id", "campaign_id")
        .sort(["person", "ts_ms", "click_id"], descending=[False, False, True])
        .collect(engine="streaming")
    )


def grouped_rows(frame: pl.DataFrame) -> Iterator[tuple[str, Iterable[tuple]]]:
    return groupby(frame.iter_rows(), key=itemgetter(0))


def attribute(sessions: pl.DataFrame, clicks: pl.DataFrame, channels: dict[str, str]) -> pl.DataFrame:
    """Credit and assist sessions in O(sessions + clicks + emitted assists)."""
    session_rows = sessions.select("person", "session_start", "day", "revenue_cents", "purchasing")
    sg = iter(grouped_rows(session_rows))
    cg = iter(grouped_rows(clicks))
    s_cur = next(sg, None)
    c_cur = next(cg, None)
    totals: dict[tuple[str, object], list[int]] = defaultdict(lambda: [0, 0, 0, 0])

    while s_cur is not None:
        person, person_sessions = s_cur
        while c_cur is not None and c_cur[0] < person:
            c_cur = next(cg, None)
        person_clicks = list(c_cur[1]) if c_cur is not None and c_cur[0] == person else []
        if c_cur is not None and c_cur[0] == person:
            c_cur = next(cg, None)

        active: deque[tuple[int, str, str]] = deque()
        campaign_counts: Counter[str] = Counter()
        click_index = 0
        for _, start, day, revenue, purchasing in person_sessions:
            while click_index < len(person_clicks) and person_clicks[click_index][1] <= start:
                _, ts, click_id, campaign_id = person_clicks[click_index]
                active.append((ts, click_id, campaign_id))
                campaign_counts[campaign_id] += 1
                click_index += 1
            minimum = start - SEVEN_DAYS_MS
            while active and active[0][0] < minimum:
                _, _, expired_campaign = active.popleft()
                campaign_counts[expired_campaign] -= 1
                if campaign_counts[expired_campaign] == 0:
                    del campaign_counts[expired_campaign]

            credit = active[-1][2] if active else "organic"
            credited = totals[(credit, day)]
            credited[0] += 1
            credited[1] += int(purchasing)
            credited[2] += int(revenue)
            for campaign_id in campaign_counts:
                totals[(campaign_id, day)][3] += 1

        s_cur = next(sg, None)

    rows = [
        (campaign_id, "organic" if campaign_id == "organic" else channels[campaign_id], day, *values)
        for (campaign_id, day), values in totals.items()
    ]
    if not rows:
        return pl.DataFrame(schema=CAMPAIGN_SCHEMA)
    return pl.DataFrame(rows, schema=CAMPAIGN_SCHEMA, orient="row").sort(["campaign_id", "day"]).cast(CAMPAIGN_SCHEMA)


def write_output(name: str, frame: pl.DataFrame) -> None:
    folder = OUT / name
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.parquet"):
        old.unlink()
    frame.write_parquet(folder / "part-0.parquet", compression="uncompressed")


def main() -> None:
    with open(DATA / "manifest.json", encoding="utf-8") as handle:
        manifest = json.load(handle)
    start, end = epoch_ms(manifest["window_start"]), epoch_ms(manifest["window_end"])
    products = pl.scan_csv(DATA / "products.csv", schema_overrides={"product_id": pl.String, "category": pl.String})
    campaign_df = pl.read_csv(
        DATA / "campaigns.csv", schema_overrides={"campaign_id": pl.String, "channel": pl.String}
    )
    campaigns = campaign_df.lazy()
    channels = dict(campaign_df.iter_rows())
    identities = load_identities()
    sessions, user_daily = build_events(identities, products, start, end)
    clicks = build_clicks(identities, campaigns, start, end)
    campaign_daily = attribute(sessions, clicks, channels)
    write_output("user_daily", user_daily)
    write_output("campaign_daily", campaign_daily)
    print(f"wrote {user_daily.height} user_daily and {campaign_daily.height} campaign_daily rows")


if __name__ == "__main__":
    main()
