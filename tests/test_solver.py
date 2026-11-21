"""Black-box tests of the compiled C++ core; no external dependencies."""
from __future__ import annotations
import csv
from datetime import datetime, timedelta, timezone
import json
import pathlib
import subprocess
import tempfile

import pytest

ROOT=pathlib.Path(__file__).resolve().parents[1]
DAY=datetime(2026,10,1,tzinfo=timezone.utc)


def stamp(dt):return dt.strftime('%Y-%m-%dT%H:%M:%SZ')
def millis(dt):return str(int(dt.timestamp()*1000))


def setup_case(tmp_path, links='', products='p1,shoes\np2,bags\n', campaigns='c1,social\nc2,search\n'):
    data=tmp_path/'data';out=tmp_path/'output';work=tmp_path/'work'
    for d in ('events','clicks','links'): (data/d).mkdir(parents=True)
    data.joinpath('manifest.json').write_text(json.dumps({'window_start':'2026-10-01T00:00:00Z','window_end':'2026-10-15T00:00:00Z'}))
    data.joinpath('products.csv').write_text('product_id,category\n'+products)
    data.joinpath('campaigns.csv').write_text('campaign_id,channel\n'+campaigns)
    data.joinpath('links','links.csv').write_text('user_id_a,user_id_b\n'+links)
    return data,out,work


def set_rows(data, events, clicks):
    data.joinpath('events','data.csv').write_text('event_id,user_id,ts,ingest_ts,event_type,product_id,price_cents\n'+events)
    data.joinpath('clicks','data.csv').write_text('click_id,user_id,campaign_id,ts\n'+clicks)


@pytest.fixture(scope='session')
def exe(tmp_path_factory):
    path=tmp_path_factory.mktemp('compiled')/'shopping_core'
    subprocess.run(['g++','-std=c++20','-O2','-DNDEBUG','src/solver.cpp','-o',str(path)],check=True,cwd=ROOT)
    return path


def execute(exe,data,out,work):
    p=subprocess.run([str(exe),str(data),str(out),str(work)],capture_output=True,text=True,timeout=20)
    assert p.returncode==0,p.stderr
    with (work/'user_daily.csv').open() as f:us=list(csv.DictReader(f))
    with (work/'campaign_daily.csv').open() as f:cs=list(csv.DictReader(f))
    return us,cs,p.stderr


def test_exact_session_attribution_and_cross_midnight(exe,tmp_path):
    data,out,work=setup_case(tmp_path,links='z,a\na,m\nx,x\n')
    e='''e1,z,2026-10-03T23:58:10Z,2026-10-03T23:59:00Z,view,p1,
e2,m,2026-10-04T00:28:10Z,2026-10-04T00:29:00Z,cart,p1,ignored
e3,m,2026-10-04T00:58:11Z,2026-10-04T00:59:00Z,purchase,p1,0250
e4,a,2026-10-04T00:58:11Z,2026-10-04T00:59:01Z,purchase,p2,1000
e5,x,2026-10-03T00:00:00Z,2026-10-03T00:00:10Z,purchase,unknown,300
'''
    clicks='''k1,z,c1,2026-10-03T23:00:00Z
k2,m,c2,2026-10-03T23:55:00Z
k3,a,c1,2026-10-04T00:58:11Z
k4,z,c2,2026-10-04T00:58:11Z
k5,z,c2,2026-10-04T00:58:11.001Z
k6,x,c2,2026-09-26T00:00:00Z
'''
    set_rows(data,e,clicks)
    us,cs,_=execute(exe,data,out,work)
    ud={(r['user_id'],r['day']):r for r in us}
    assert len(ud)==3
    assert ud['a','2026-10-03']['sessions']=='1'
    assert ud['a','2026-10-03']['events']=='2'
    assert ud['a','2026-10-03']['revenue_cents']=='0'
    assert ud['a','2026-10-03']['top_category']==''
    assert ud['a','2026-10-04']['sessions']=='1'
    assert ud['a','2026-10-04']['events']=='2'
    assert ud['a','2026-10-04']['revenue_cents']=='1250'
    assert ud['a','2026-10-04']['top_category']=='bags'
    assert ud['x','2026-10-03']['top_category']=='unknown'
    cd={(r['campaign_id'],r['day']):r for r in cs}
    assert cd['c2','2026-10-03']['sessions']=='2'
    assert cd['c2','2026-10-03']['revenue_cents']=='300'
    assert cd['c1','2026-10-04']['sessions']=='1' # k3 before k4 lexicographically
    assert cd['c1','2026-10-04']['revenue_cents']=='1250'
    assert cd['c1','2026-10-03']['sessions']=='0'
    assert cd['c1','2026-10-03']['assisted_sessions']=='1'
    assert cd['c2','2026-10-03']['assisted_sessions']=='2'
    assert cd['c1','2026-10-04']['assisted_sessions']=='1'
    assert cd['c2','2026-10-04']['assisted_sessions']=='1'


def test_dedup_before_validation_late_and_malformed(exe,tmp_path):
    data,out,work=setup_case(tmp_path)
    e='''a1,u1,2026-10-03T24:00:00Z,2026-10-03T00:00:00Z,purchase,p1,1000
a1,u1,2026-10-03T00:00:00Z,2026-10-03T00:05:00Z,purchase,p1,1000
late,u1,2026-10-03T00:00:00Z,2026-10-04T00:00:01Z,view,p1,
exact,u1,2026-10-03T00:00:00Z,2026-10-04T00:00:00Z,view,p1,
malformed,u1,2026-10-03T01:00:00Z,2026-10-03T01:00:01Z,view,p1
badPrice,u1,2026-10-03T01:00:00Z,2026-10-03T01:00:01Z,purchase,p1,1000\r
nonASCII,u1,2026-10-03T01:00:00Z,2026-10-03T01:00:01Z,purchase,p1,٢٥٠
quoted,"u1",2026-10-03T01:00:00Z,2026-10-03T01:00:01Z,cart,p1,""
'''
    set_rows(data,e,'')
    us,cs,_=execute(exe,data,out,work)
    assert len(us)==1
    assert us[0]['sessions']=='2' # exact + quoted, one hour apart
    assert us[0]['events']=='2'
    assert us[0]['revenue_cents']=='0'
    assert us[0]['top_category']==''
    assert len(cs)==1 and cs[0]['campaign_id']=='organic'
    assert cs[0]['sessions']=='2' and cs[0]['assisted_sessions']=='0'


def test_timestamp_offsets_unlinked_min_and_7_day_boundary(exe,tmp_path):
    data,out,work=setup_case(tmp_path,links='z,q\na,z\n')
    e='''x1,q,2026-10-03T19:58:10-04:00,2026-10-04T00:00:00Z,purchase,p1,0500
x2,q,1791071890000,2026-10-04T00:00:01Z,cart,p1,
'''
    clicks='''cl1,z,c1,2026-09-26T23:58:10Z
cl2,z,c2,2026-09-26T23:58:09Z
'''
    # x1 normalizes to Oct3 23:58:10; cl1 exactly 7 days before
    set_rows(data,e,clicks)
    us,cs,_=execute(exe,data,out,work)
    assert any(r['user_id']=='a' for r in us)
    assert all(r['campaign_id']!='c2' for r in cs)
    assert any(r['campaign_id']=='c1' and r['assisted_sessions']=='1' for r in cs)


def test_large_group_interval_union_does_not_lose_nonoverlapping_intervals(exe,tmp_path):
    data,out,work=setup_case(tmp_path)
    # > 12k cross-product, forced interval-union branch; sessions every hour.
    events=[];clicks=[]
    base=DAY+timedelta(days=2)
    for i in range(201):
        t=base+timedelta(hours=i)
        events.append(f'e{i},whale,{millis(t)},{stamp(t+timedelta(minutes=1))},purchase,p1,100')
    for i in range(201):
        t=base-timedelta(days=1)+timedelta(hours=i)
        clicks.append(f'cl{i},whale,{"c1" if i%2 else "c2"},{millis(t)}')
    set_rows(data,'\n'.join(events)+'\n','\n'.join(clicks)+'\n')
    us,cs,log=execute(exe,data,out,work)
    assert sum(int(r['sessions']) for r in us)==201
    assert sum(int(r['revenue_cents']) for r in us)==20100
    assert sum(int(r['sessions']) for r in cs)==201
    assert sum(int(r['assisted_sessions']) for r in cs)==402 # both campaigns assist all 201 sessions


def test_category_tie_byte_wise_and_ids_case_sensitive(exe,tmp_path):
    data,out,work=setup_case(tmp_path,products='p1,zeta\np2,Alpha\n')
    t='2026-10-05T12:00:00Z';ing='2026-10-05T12:00:01Z'
    es=f'a,U1,{t},{ing},purchase,p1,100\nb,U1,{t},{ing},purchase,p2,100\nc,u1,{t},{ing},view,p1,\n'
    set_rows(data,es,'')
    us,_,_=execute(exe,data,out,work)
    assert len(us)==2
    assert [r['top_category'] for r in us if r['user_id']=='U1']==['Alpha']


def test_no_events_writes_valid_headers(exe,tmp_path):
    data,out,work=setup_case(tmp_path)
    set_rows(data,'','')
    us,cs,_=execute(exe,data,out,work)
    assert us==[] and cs==[]


def test_randomized_independent_attribution_oracle_large_group(exe,tmp_path):
    # Exercise interval-union with DISJOINT windows, shared timestamps, and random campaigns.
    import random
    rng=random.Random(4311)
    data,out,work=setup_case(tmp_path)
    base=DAY+timedelta(days=1)
    sessions=[base+timedelta(minutes=140*i) for i in range(120)]
    # 90 clicks on Sep 26 and 100 on Oct 13; disjoint seven-day coverage intervals.
    clickrows=[]
    for j in range(190):
        if j<90: t=DAY-timedelta(days=5)+timedelta(minutes=rng.randrange(150))
        else: t=DAY+timedelta(days=12)+timedelta(minutes=rng.randrange(150))
        c=rng.choice(['c1','c2'])
        clickrows.append((f'z{j:03}',t,c))
    # Deliberate same-timestamp clicks from different campaigns to test click-ID tie-break.
    clickrows += [('a-tie',sessions[1],'c1'),('z-tie',sessions[1],'c2')]
    events='\n'.join(f'e{i},client,{millis(t)},{stamp(t+timedelta(minutes=1))},purchase,p1,100'
                      for i,t in enumerate(sessions))+'\n'
    clicks='\n'.join(f'{cid},client,{c},{millis(t)}' for cid,t,c in clickrows)+'\n'
    set_rows(data,events,clicks)
    us,cs,_=execute(exe,data,out,work)
    actual={(r['campaign_id'],r['day']):{k:int(r[k]) for k in
           ('sessions','purchasing_sessions','revenue_cents','assisted_sessions')} for r in cs}
    from collections import defaultdict
    oracle=defaultdict(lambda:dict(sessions=0,purchasing_sessions=0,revenue_cents=0,assisted_sessions=0))
    for s in sessions:
        valid=[(cid,t,c) for cid,t,c in clickrows if timedelta(0)<=s-t<=timedelta(days=7)]
        if valid:
            best=sorted(valid,key=lambda v:(-int(v[1].timestamp()*1000),v[0].encode()))[0]
            credited=best[2]
        else: credited='organic'
        key=(credited,s.date().isoformat())
        oracle[key]['sessions']+=1;oracle[key]['purchasing_sessions']+=1;oracle[key]['revenue_cents']+=100
        for camp in {c for cid,t,c in valid}:oracle[camp,s.date().isoformat()]['assisted_sessions']+=1
    assert dict(oracle)==actual
    assert sum(int(x['sessions']) for x in us)==120


def test_case_sensitive_ids_and_timestamp_invalidations(exe,tmp_path):
    data,out,work=setup_case(tmp_path)
    rows_data=[
      ('yes','User','2026-10-03T23:58:10Z','2026-10-03T23:59:00Z','view','p1',''),
      ('yes2',' User','2026-10-03T23:58:10Z','2026-10-03T23:59:00Z','view','p1',''),
      ('bad1','User','2026-02-29T00:00:00Z','2026-10-03T23:59:00Z','view','p1',''),
      ('bad2','User','2026-10-03T23:58:10+24:00','2026-10-03T23:59:00Z','view','p1',''),
      ('bad3','User','2026-10-03t23:58:10Z','2026-10-03T23:59:00Z','view','p1',''),
    ]
    set_rows(data,'\n'.join(','.join(r) for r in rows_data)+'\n','')
    us,_,_=execute(exe,data,out,work)
    assert {r['user_id'] for r in us}=={'User',' User'}
    assert all(r['events']=='1' for r in us)
