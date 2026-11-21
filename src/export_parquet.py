"""Convert validated C++ aggregation CSVs to the two official Parquet output schemas."""
from __future__ import annotations
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time


def sql_path(path: pathlib.Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def main() -> int:
    import duckdb

    data = pathlib.Path(os.environ.get("SHOPPING_DATA", os.environ.get("DATA_DIR", "/data")))
    output = pathlib.Path(os.environ.get("SHOPPING_OUTPUT", os.environ.get("OUTPUT_DIR", "/output")))
    work_base = pathlib.Path(os.environ.get("SHOPPING_WORK_BASE", os.environ.get("SCRATCH_DIR", "/scratch")))
    work = pathlib.Path(tempfile.mkdtemp(prefix="shopping-", dir=work_base))
    keep = os.environ.get("SHOPPING_KEEP_WORK") == "1"
    began = time.monotonic()
    try:
        binary = pathlib.Path(__file__).resolve().parent.parent / "shopping_core"
        cmd = [str(binary), str(data), str(output), str(work)]
        subprocess.run(cmd, check=True)
        for part in ("user_daily", "campaign_daily"):
            folder = output / part
            folder.mkdir(parents=True, exist_ok=True)
            for old in folder.glob('*.parquet'):
                old.unlink()
        con = duckdb.connect(database=":memory:")
        try:
            threads = max(1, min(8, int(os.environ.get("NCPU", "8"))))
            con.execute(f"SET threads = {threads}")
            spill_dir = work / "duckdb_spill"
            spill_dir.mkdir(parents=True, exist_ok=True)
            con.execute(f"SET temp_directory = {sql_path(spill_dir)}")
            user_path = sql_path(work / "user_daily.csv")
            campaign_path = sql_path(work / "campaign_daily.csv")
            user_dst = sql_path(output / "user_daily" / "part-0.parquet")
            campaign_dst = sql_path(output / "campaign_daily" / "part-0.parquet")
            con.execute(f"""
                COPY (
                    SELECT
                        CAST(user_id AS VARCHAR) AS user_id,
                        CAST(day AS DATE) AS day,
                        CAST(sessions AS BIGINT) AS sessions,
                        CAST(events AS BIGINT) AS events,
                        CAST(revenue_cents AS BIGINT) AS revenue_cents,
                        NULLIF(CAST(top_category AS VARCHAR), '') AS top_category
                    FROM read_csv({user_path},
                        header=true, auto_detect=false,
                        columns={{'user_id':'VARCHAR','day':'VARCHAR',
                                 'sessions':'VARCHAR','events':'VARCHAR',
                                 'revenue_cents':'VARCHAR','top_category':'VARCHAR'}},
                        delim=',', quote='"', escape='"',
                        nullstr='')
                ) TO {user_dst} (FORMAT PARQUET, COMPRESSION SNAPPY)
            """)
            con.execute(f"""
                COPY (
                    SELECT
                        CAST(campaign_id AS VARCHAR) AS campaign_id,
                        CAST(channel AS VARCHAR) AS channel,
                        CAST(day AS DATE) AS day,
                        CAST(sessions AS BIGINT) AS sessions,
                        CAST(purchasing_sessions AS BIGINT) AS purchasing_sessions,
                        CAST(revenue_cents AS BIGINT) AS revenue_cents,
                        CAST(assisted_sessions AS BIGINT) AS assisted_sessions
                    FROM read_csv({campaign_path},
                        header=true, auto_detect=false,
                        columns={{'campaign_id':'VARCHAR','channel':'VARCHAR',
                                 'day':'VARCHAR','sessions':'VARCHAR',
                                 'purchasing_sessions':'VARCHAR',
                                 'revenue_cents':'VARCHAR','assisted_sessions':'VARCHAR'}},
                        delim=',', quote='"', escape='"',
                        nullstr='')
                ) TO {campaign_dst} (FORMAT PARQUET, COMPRESSION SNAPPY)
            """)
        finally:
            con.close()
        print(f"Shopping Sessions Parquet outputs written; elapsed {time.monotonic()-began:.2f}s", file=sys.stderr)
        return 0
    finally:
        if keep:
            print(f"Kept temporary summaries at {work}", file=sys.stderr)
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
