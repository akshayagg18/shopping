"""Independent pure-Python specification oracle versus optimized C++ solver."""
from __future__ import annotations
import csv
from collections import defaultdict
from datetime import datetime,timedelta,timezone
import json
import pathlib
import random
import subprocess

import pytest

BASE=datetime(2026,10,1,tzinfo=timezone.utc)
ROOT=pathlib.Path(__file__).resolve().parents[1]
MILLIS=1000
DAY=86400000
WEEK=7*DAY
GAP=30*60*1000


def ms(t):return int(t.timestamp()*1000)
def ts(t):return t.strftime('%Y-%m-%dT%H:%M:%SZ')


@pytest.fixture(scope='session')
def core(tmp_path_factory):
    exe=tmp_path_factory.mktemp('oraclebin')/'shopping_core'
    subprocess.run(['g++','-std=c++20','-O2','-DNDEBUG','src/solver.cpp','-o',str(exe)],cwd=ROOT,check=True)
    return exe


def oracle(evs,clicks,uid_canonical):
    evmap={}
    for event_id,user,t,ingest,kind,prod,price in evs:
        if event_id not in evmap or ingest<evmap[event_id][3]:evmap[event_id]=(event_id,user,t,ingest,kind,prod,price)
    eligible=[]
    for row in evmap.values():
        _,u,t,ing,kind,prod,price=row
        if t is None or not (ms(BASE)<=t<ms(BASE+timedelta(days=14))) or ing-t>DAY or kind not in ('view','cart','purchase') or not prod:continue
        if kind=='purchase' and (price is None or not 1<=price<=10000000):continue
        eligible.append(row)
    by_person=defaultdict(list)
    for row in eligible:by_person[uid_canonical[row[1]]].append(row)
    cl_by_person=defaultdict(dict)
    for cid,u,c,t in clicks:
        if u in uid_canonical and ms(BASE)-WEEK<=t<ms(BASE+timedelta(days=14)):
            cl_by_person[uid_canonical[u]][cid]=(cid,u,c,t)
    campaign=defaultdict(lambda:dict(sessions=0,purchasing_sessions=0,revenue_cents=0,assisted_sessions=0))
    user=[]
    for person,erows in by_person.items():
        erows.sort(key=lambda r:r[2]); sessions=[]
        for e in erows:
            if not sessions or e[2]-sessions[-1]['last']>GAP:
                sessions.append(dict(start=e[2],last=e[2],events=[],rev=0,cat=defaultdict(int),purchase=False))
            s=sessions[-1];s['last']=e[2];s['events'].append(e)
            if e[4]=='purchase':
                s['rev']+=e[6];s['purchase']=True
                s['cat'][{'p1':'shoes','p2':'bags'}.get(e[5],'unknown')]+=e[6]
        ud=defaultdict(lambda:dict(sessions=0,events=0,revenue_cents=0,cat=defaultdict(int)))
        pcl=list(cl_by_person[person].values())
        for s in sessions:
            day=datetime.fromtimestamp(s['start']/1000,timezone.utc).date().isoformat()
            d=ud[day];d['sessions']+=1;d['events']+=len(s['events']);d['revenue_cents']+=s['rev']
            for c,n in s['cat'].items():d['cat'][c]+=n
            good=[c for c in pcl if 0<=s['start']-c[3]<=WEEK]
            if good:
                best=min(good,key=lambda c:(-c[3],c[0].encode()))
                credit=best[2]
            else: credit='organic'
            cd=campaign[credit,day];cd['sessions']+=1;cd['purchasing_sessions']+=int(s['purchase']);cd['revenue_cents']+=s['rev']
            for cid in set(c[2] for c in good):campaign[cid,day]['assisted_sessions']+=1
        for day,d in ud.items():
            best=min(((-rev,category.encode(),category) for category,rev in d['cat'].items()),default=None)
            user.append((person,day,d['sessions'],d['events'],d['revenue_cents'],'' if best is None else best[2]))
    camp=[]
    for (cid,day),stats in campaign.items():
        camp.append((cid,{'c1':'social','c2':'search','organic':'organic'}[cid],day,
            stats['sessions'],stats['purchasing_sessions'],stats['revenue_cents'],stats['assisted_sessions']))
    return sorted(user),sorted(camp)


def test_randomized_complete_pipeline(core,tmp_path):
    for seed in range(6):
        r=random.Random(1000+seed)
        case=tmp_path/f'case{seed}'; data=case/'data';out=case/'out';work=case/'work'
        for d in ('events','clicks','links'): (data/d).mkdir(parents=True)
        (data/'manifest.json').write_text(json.dumps({'window_start':'2026-10-01T00:00:00Z','window_end':'2026-10-15T00:00:00Z'}))
        (data/'products.csv').write_text('product_id,category\np1,shoes\np2,bags\n')
        (data/'campaigns.csv').write_text('campaign_id,channel\nc1,social\nc2,search\n')
        users=[];uid_canonical={};links=[]
        for i in range(10):
            ids=[f'user{i:03}_a',f'user{i:03}_b',f'user{i:03}_c']
            smallest=f'0_unused_{i:03}' if i%2==0 else min(ids)
            if i%2==0:links.append((smallest,ids[0]))
            links.extend(zip(ids,ids[1:]))
            for uid in ids:uid_canonical[uid]=smallest
            users.append(ids)
        (data/'links'/'a.csv').write_text('user_id_a,user_id_b\n'+'\n'.join(','.join(x) for x in links)+'\n')
        events=[];clicks=[];event_lines=[]
        for i in range(1200):
            user=r.choice(r.choice(users))
            t=BASE+timedelta(days=r.randrange(14),milliseconds=r.randrange(86400000))
            ing=t+timedelta(hours=r.randrange(30))
            kind=r.choice(['view','cart','purchase'])
            product=r.choice(['p1','p2','not_in_products'])
            price=(r.randrange(1,3000) if kind=='purchase' else 0)
            if kind=='purchase' and r.randrange(12)==0:price=0
            eid=f'e{i:07}'
            row=(eid,user,ms(t),ms(ing.replace(microsecond=0)),kind,product,price)
            events.append(row)
            iso=ts(ing)
            if i%5==0:
                value=str(ms(t))
            elif i%5==1:
                value=(t+timedelta(hours=5)).strftime('%Y-%m-%dT%H:%M:%S+05:00')
                # ensure timestamp is at an exact second for the offset representation
                t=t.replace(microsecond=0);row=(eid,user,ms(t),ms(ing.replace(microsecond=0)),kind,product,price);events[-1]=row
            else:
                value=ts(t);t=t.replace(microsecond=0);row=(eid,user,ms(t),ms(ing.replace(microsecond=0)),kind,product,price);events[-1]=row
            event_lines.append(f'{eid},{user},{value},{iso},{kind},{product},{price if kind=="purchase" else ""}')
            if i%37==0:
                later=ing+timedelta(minutes=2)
                dup=(eid,user,ms(t),ms(later.replace(microsecond=0)),kind,product,price)
                events.append(dup)
                event_lines.append(f'{eid},{user},{value},{ts(later)},{kind},{product},{price if kind=="purchase" else ""}')
        for i in range(200):
            uid=r.choice(r.choice(users))
            t=BASE+timedelta(days=r.randrange(-7,14),milliseconds=r.randrange(86400000))
            cid=f'cl{i:06}'
            camp=r.choice(['c1','c2'])
            clicks.append((cid,uid,camp,ms(t)))
        r.shuffle(event_lines)
        (data/'events'/'a.csv').write_text('event_id,user_id,ts,ingest_ts,event_type,product_id,price_cents\n'+'\n'.join(event_lines)+'\n')
        r.shuffle(clicks)
        (data/'clicks'/'a.csv').write_text('click_id,user_id,campaign_id,ts\n'+'\n'.join(f'{cid},{uid},{camp},{num}' for cid,uid,camp,num in clicks)+'\n')
        p=subprocess.run([str(core),str(data),str(out),str(work)],capture_output=True,text=True,timeout=20)
        assert p.returncode==0,p.stderr
        with (work/'user_daily.csv').open() as f:
            users_actual=sorted((row['user_id'],row['day'],int(row['sessions']),int(row['events']),
                                 int(row['revenue_cents']),row['top_category']) for row in csv.DictReader(f))
        with (work/'campaign_daily.csv').open() as f:
            campaigns_actual=sorted((row['campaign_id'],row['channel'],row['day'],int(row['sessions']),
               int(row['purchasing_sessions']),int(row['revenue_cents']),int(row['assisted_sessions'])) for row in csv.DictReader(f))
        expected_user,expected_campaign=oracle(events,clicks,uid_canonical)
        assert users_actual==expected_user, f'seed {seed}: user table mismatch'
        assert campaigns_actual==expected_campaign, f'seed {seed}: campaign table mismatch'
