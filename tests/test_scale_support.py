import asyncio
import os
import pytest
from fastapi import HTTPException
from redis.exceptions import ConnectionError
from app.config import settings
from app.db import SessionLocal
from app.models import Notification
from .test_workflows import req
from .test_auth_storage import cover_body

def test_disabled_uploads_and_feature_flag(client,actors,monkeypatch):
    monkeypatch.setattr(settings,'uploads_enabled',False)
    assert client.get('/v1/auth/options').json()['uploads_enabled'] is False
    req(client,actors,'student','PUT','/me/cover',cover_body(),code=403)

def test_notification_summary_and_bulk_read_are_private(client,actors):
    with SessionLocal() as db:
        for role in ['student','other']:
            for i in range(105):db.add(Notification(user_id=actors[role]['id'],message='Notice',resource_id='event'))
        db.commit()
    assert req(client,actors,'student','GET','/notifications/summary')=={'unread':105}
    req(client,actors,'student','POST','/notifications/read-all')
    assert req(client,actors,'student','GET','/notifications/summary')=={'unread':0}
    assert req(client,actors,'other','GET','/notifications/summary')=={'unread':105}

def test_shared_limiter_fails_closed(monkeypatch):
    from app import rate_limit
    class Broken:
        async def eval(self,*args):raise ConnectionError('private-server-details')
    monkeypatch.setattr(rate_limit,'redis_client',lambda:Broken())
    with pytest.raises(HTTPException) as err:asyncio.run(rate_limit.shared_auth_limit('test','account','/login'))
    assert err.value.status_code==503
    assert 'private-server-details' not in err.value.detail

@pytest.mark.skipif(not os.environ.get('TEST_REDIS_URL'),reason='Dedicated Redis service required')
def test_shared_limiter_real_redis(monkeypatch):
    from app import rate_limit
    from redis.asyncio import Redis
    from uuid import uuid4
    async def run():
        connection=Redis.from_url(os.environ['TEST_REDIS_URL'])
        monkeypatch.setattr(rate_limit,'redis_client',lambda:connection)
        ip=str(uuid4());key=str(uuid4())
        results=await asyncio.gather(*[rate_limit.shared_auth_limit(ip,key,'/login') for _ in range(20)],return_exceptions=True)
        assert sum(x is None for x in results)==10
        assert sum(isinstance(x,HTTPException) and x.status_code==429 for x in results)==10
        await rate_limit.shared_auth_limit(ip,str(uuid4()),'/login')
        await connection.aclose()
    asyncio.run(run())


def test_referenced_names_omit_sensitive_fields_and_hidden_accounts(client,actors):
    from app.models import User
    with SessionLocal() as db:
        db.get(User,actors['other']['id']).active=False;db.commit()
    ids=','.join(actors[r]['id'] for r in ['student','other','admin'])
    assert req(client,actors,'student','GET','/people?ids='+ids)==[{'id':actors['student']['id'],'name':'student'}]
