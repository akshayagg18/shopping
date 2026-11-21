"""Optional synthetic throughput smoke test (NOT an official challenge benchmark).
Run: python tests/benchmark_synthetic.py --events 500000
"""
import argparse
from datetime import datetime,timezone,timedelta
import json
import pathlib
import random
import subprocess
import tempfile
import time

START=datetime(2026,10,1,tzinfo=timezone.utc)

def run(count:int, seed:int=42):
    rng=random.Random(seed)
    root=pathlib.Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='shop-bench-') as temp:
        base=pathlib.Path(temp); data=base/'data';out=base/'out';work=base/'work'
        for part in ('events','clicks','links'):(data/part).mkdir(parents=True)
        (data/'manifest.json').write_text(json.dumps({'window_start':'2026-10-01T00:00:00Z','window_end':'2026-10-15T00:00:00Z'}))
        (data/'products.csv').write_text('product_id,category\n'+'\n'.join(f'p{i},cat{i%20}' for i in range(200))+'\n')
        (data/'campaigns.csv').write_text('campaign_id,channel\n'+'\n'.join(f'c{i},channel{i%5}' for i in range(2000))+'\n')
        people=max(1,count//32)
        with (data/'links'/'part.csv').open('w') as f:
            f.write('user_id_a,user_id_b\n')
            for i in range(people//3):f.write(f'u{i},u{i}_alt\n')
        epoch=int(START.timestamp()*1000)
        t=time.perf_counter()
        with (data/'events'/'part.csv').open('w') as f:
            f.write('event_id,user_id,ts,ingest_ts,event_type,product_id,price_cents\n')
            for i in range(count):
                uid=rng.randrange(people)
                if uid<people//3 and rng.randrange(2): user=f'u{uid}_alt'
                else:user=f'u{uid}'
                ts=epoch+rng.randrange(14*86400000)
                dt=datetime.fromtimestamp((ts//1000+60),timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                kind=('view','cart','purchase')[rng.randrange(3)]
                price=rng.randrange(100,3000) if kind=='purchase' else ''
                f.write(f'e{i},{user},{ts},{dt},{kind},p{rng.randrange(200)},{price}\n')
        with (data/'clicks'/'part.csv').open('w') as f:
            f.write('click_id,user_id,campaign_id,ts\n')
            for i in range(max(1,count//10)):
                uid=rng.randrange(people)
                ts=epoch-7*86400000+rng.randrange(21*86400000)
                f.write(f'cl{i},u{uid},c{rng.randrange(2000)},{ts}\n')
        generated=time.perf_counter()-t
        exe=root/'shopping_core'
        if not exe.exists():
            subprocess.run(['g++','-std=c++20','-O3','-DNDEBUG','src/solver.cpp','-o','shopping_core'],cwd=root,check=True)
        t=time.perf_counter()
        result=subprocess.run([str(exe),str(data),str(out),str(work)],capture_output=True,text=True)
        elapsed=time.perf_counter()-t
        if result.returncode:raise RuntimeError(result.stderr)
        print(json.dumps({'events_input':count,'clicks_input':max(1,count//10),'synthetic_generation_sec':round(generated,3),
                          'core_runtime_sec':round(elapsed,3),'core_events_per_sec':round(count/elapsed),
                          'notes':'synthetic input; excludes Parquet conversion and Docker; NOT official scoring'},indent=2))
        print(result.stderr)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--events',type=int,default=500000)
    parser.add_argument('--seed',type=int,default=42)
    args=parser.parse_args();run(args.events,args.seed)
