"""Disposable API capacity probe; never point at a live college database.
DATABASE_URL must name bmsit_loadtest (PostgreSQL) or end in loadtest.db (SQLite).
python -m tests.load_test --confirm-disposable --clients 50 --requests 1000
"""
import argparse,asyncio,json,os,statistics,subprocess,sys,time,tempfile
from datetime import timedelta
from pathlib import Path
from sqlalchemy.engine import make_url
import httpx

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-disposable',action='store_true',required=True)
    parser.add_argument('--clients',type=int,default=50)
    parser.add_argument('--requests',type=int,default=1000)
    args=parser.parse_args()
    url=make_url(os.environ['DATABASE_URL'])
    if not (url.database=='bmsit_loadtest' or (url.drivername=='sqlite' and str(url.database).endswith('loadtest.db'))):
        raise SystemExit('Refusing: expected dedicated bmsit_loadtest database or loadtest.db')
    if not 1<=args.clients<=200 or not 100<=args.requests<=20000:raise SystemExit('Use 1–200 clients and 100–20000 requests')
    from app.db import Base,engine,SessionLocal
    from app.models import User,Club,Event,Notification,now
    from app.security import issue_token,passwords
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine)
    with SessionLocal() as db:
        hashed=passwords.hash('Disposable-capacity-fixture-only-123!')
        users=[User(email=f'load{i}@example.com',usn=f'LOAD{i}',name=f'Student {i:04}',password_hash=hashed,approved=True) for i in range(1000)]
        db.add_all(users);db.flush()
        club=Club(name='Capacity fixture',description='Disposable data',category='Technology');db.add(club);db.flush()
        event=Event(club_id=club.id,title='Load test event',description='Fixture',kind='Hackathon',starts_at=now()+timedelta(days=7),venue='Fixture',capacity=10,status='approved');db.add(event);db.flush()
        event_id=event.id
        tokens=[issue_token(db,u) for u in users[:args.clients]]
        db.add_all([Notification(user_id=u.id,message=f'Fixture {i}',resource_id=event_id) for u in users for i in range(10)])
        db.commit()
    server=subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8019','--workers','2','--no-access-log'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    async def probe():
        async with httpx.AsyncClient(trust_env=False,base_url='http://127.0.0.1:8019',timeout=20,limits=httpx.Limits(max_connections=args.clients,max_keepalive_connections=args.clients)) as client:
            for _ in range(100):
                try:
                    if (await client.get('/ready')).status_code==200:break
                except httpx.TransportError:pass
                await asyncio.sleep(.1)
            else:raise RuntimeError('Load-test server failed to start')
            gate=asyncio.Semaphore(args.clients);elapsed=[];failures=[]
            paths=['/v1/me','/v1/students?limit=24&q=Student','/v1/events?limit=50','/v1/notifications/summary','/v1/notifications?limit=50']
            async def request(i):
                async with gate:
                    start=time.perf_counter()
                    try:
                        response=await client.get(paths[i%len(paths)],headers={'Authorization':'Bearer '+tokens[i%len(tokens)]})
                        if response.status_code!=200:failures.append(response.status_code)
                    except httpx.TransportError:failures.append('transport')
                    elapsed.append((time.perf_counter()-start)*1000)
            start=time.perf_counter();await asyncio.gather(*(request(i) for i in range(args.requests)));duration=time.perf_counter()-start
            result={'database':url.get_backend_name(),'registered_users':1000,'notification_rows':10000,'concurrent_clients':args.clients,'workers':2,'requests':args.requests,'failed_requests':len(failures),'duration_s':round(duration,2),'requests_per_second':round(args.requests/duration,2),'p50_ms':round(statistics.median(elapsed),2),'p95_ms':round(sorted(elapsed)[int(.95*(len(elapsed)-1))],2),'scope':'Authenticated read API only; excludes login, SMTP, uploads and full browser workload'}
            print(json.dumps(result,indent=2))
            if failures:raise RuntimeError(f'{len(failures)} requests failed')
    try:asyncio.run(probe())
    finally:server.terminate();server.wait(timeout=15)
if __name__=='__main__':main()
