"""Check output tables against an OFFICIAL dev-answer directory with DuckDB.

Usage: python scripts/compare_parquet.py /path/to/dev-answer /path/to/our-output
If official paths differ, pass the two folders containing user_daily and campaign_daily.
"""
from __future__ import annotations
import argparse
import pathlib
import sys

USERS=['user_id','day','sessions','events','revenue_cents','top_category']
CAMPAIGNS=['campaign_id','channel','day','sessions','purchasing_sessions','revenue_cents','assisted_sessions']


def find_table(base: pathlib.Path, table: str):
    # Supports the official dev-answer's CSV files or arbitrary parquet parts in a table folder.
    candidates=[base / (table + '.csv'), base/table/(table+'.csv'), base/table,
                base/'output'/table, base/'answers'/(table+'.csv'), base/'answers'/table]
    for c in candidates:
        if c.is_file() and c.suffix=='.csv':return 'csv',[c]
        if c.is_dir():
            p=list(c.glob('*.parquet'))
            if p:return 'parquet',p
            q=list(c.glob('*.csv'))
            if q:return 'csv',q
    # Last-resort find for idiosyncratic official zip structure.
    files=list(base.rglob(table+'.csv'))
    if files:return 'csv',files
    directories=[p for p in base.rglob(table) if p.is_dir()]
    for d in directories:
        parts=list(d.glob('*.parquet'))
        if parts:return 'parquet',parts
    raise FileNotFoundError(f'Could not locate {table} under {base}')


def scan(con, root, name, cols):
    kind,paths=find_table(root,name)
    paths=sorted(paths)
    path_literals=','.join("'"+str(path).replace("'","''")+"'" for path in paths)
    expression=f'[{path_literals}]' if len(paths)>1 else path_literals
    if kind=='csv':
        fields=','.join("'"+c+"':'VARCHAR'" for c in cols)
        table=f"read_csv({expression},header=true,auto_detect=false,columns={{{fields}}})"
    else:
        table=f'read_parquet({expression})'
    parts=[]
    for c in cols:
        if c=='day':part=f'CAST({c} AS DATE) AS {c}'
        elif c in ('user_id','top_category','campaign_id','channel'):
            part=f'CAST({c} AS VARCHAR) AS {c}'
            if c=='top_category' and kind=='csv':part=f"NULLIF(CAST({c} AS VARCHAR),'') AS {c}"
        else:part=f'CAST({c} AS BIGINT) AS {c}'
        parts.append(part)
    return 'SELECT '+','.join(parts)+' FROM '+table


def main():
    p=argparse.ArgumentParser()
    p.add_argument('expected',type=pathlib.Path)
    p.add_argument('actual',type=pathlib.Path)
    args=p.parse_args()
    import duckdb
    con=duckdb.connect(':memory:')
    status=0
    try:
        for name,cols in [('user_daily',USERS),('campaign_daily',CAMPAIGNS)]:
            a=scan(con,args.expected,name,cols)
            b=scan(con,args.actual,name,cols)
            # EXCEPT ALL catches missing and duplicate rows, independent of ordering.
            missing=con.execute(f'SELECT COUNT(*) FROM (({a}) EXCEPT ALL ({b}))').fetchone()[0]
            extra=con.execute(f'SELECT COUNT(*) FROM (({b}) EXCEPT ALL ({a}))').fetchone()[0]
            n_expected=con.execute(f'SELECT COUNT(*) FROM ({a})').fetchone()[0]
            n_actual=con.execute(f'SELECT COUNT(*) FROM ({b})').fetchone()[0]
            print(f'{name}: expected={n_expected} actual={n_actual} missing={missing} extra={extra}')
            if missing or extra:status=1
    finally:
        con.close()
    if status==0:print('PASS: Both output tables match the provided answers exactly (after accepted numeric-width casts).')
    else: print('FAIL: One or both tables differ.',file=sys.stderr)
    return status

if __name__=='__main__':raise SystemExit(main())
