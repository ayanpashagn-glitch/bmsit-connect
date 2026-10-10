import base64
from datetime import timedelta
from io import BytesIO
from PIL import Image
from sqlalchemy import select
from app.db import SessionLocal
from app.models import EmailOTP, User, now
from app.security import passwords
from .test_workflows import req, setup_club, FUTURE

def signup(otp='123456'):
    return {'name':'New student','email':'new@example.com','usn':'NEW123','password':'strong-test-pass-123','otp':otp}

def test_otp_delivery_expiry_lockout_resend_and_consumption(client,monkeypatch):
    sent=[]
    monkeypatch.setattr('app.main.send_otp',lambda email,code: sent.append((email,code)))
    assert client.post('/v1/auth/register',json=signup()).status_code==422
    r=client.post('/v1/auth/request-otp',json={'email':'new@example.com'})
    assert r.status_code==200 and sent[0][1] not in r.text
    first=sent[0][1]
    with SessionLocal() as db:
        row=db.get(EmailOTP,'new@example.com')
        assert row.code_hash!=first and passwords.verify(first,row.code_hash)
    assert client.post('/v1/auth/request-otp',json={'email':'new@example.com'}).status_code==429
    wrong='000000' if first!='000000' else '111111'
    for _ in range(5): assert client.post('/v1/auth/register',json=signup(wrong)).status_code==422
    assert client.post('/v1/auth/register',json=signup(first)).status_code==422
    with SessionLocal() as db:
        row=db.get(EmailOTP,'new@example.com');row.sent_at=now()-timedelta(minutes=2);db.commit()
    assert client.post('/v1/auth/request-otp',json={'email':'new@example.com'}).status_code==200
    second=sent[-1][1]
    with SessionLocal() as db:
        row=db.get(EmailOTP,'new@example.com');row.expires_at=now()-timedelta(seconds=1);db.commit()
    assert client.post('/v1/auth/register',json=signup(second)).status_code==422
    with SessionLocal() as db:
        row=db.get(EmailOTP,'new@example.com');row.expires_at=now()+timedelta(minutes=10);db.commit()
    assert client.post('/v1/auth/register',json=signup(second)).status_code==201
    assert client.post('/v1/auth/register',json=signup(second)).status_code==422
    with SessionLocal() as db: assert db.get(EmailOTP,'new@example.com') is None
    assert client.post('/v1/auth/login',json={'email':'new@example.com','password':'strong-test-pass-123'}).status_code==200

def test_mail_failure_domain_gate_and_extra_roles(client,monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings,'allowed_email_domains',['college.example'])
    assert client.post('/v1/auth/request-otp',json={'email':'new@example.com'}).status_code==422
    monkeypatch.setattr(settings,'allowed_email_domains',[])
    def fail(*args): raise RuntimeError('SECRET SMTP PASSWORD')
    monkeypatch.setattr('app.main.send_otp',fail)
    r=client.post('/v1/auth/request-otp',json={'email':'new@example.com'})
    assert r.status_code==503 and 'SECRET' not in r.text
    with SessionLocal() as db: assert db.get(EmailOTP,'new@example.com') is None
    assert client.post('/v1/auth/register',json={**signup(),'admin':True}).status_code==422

def test_coordinator_request_approval_and_member_permissions(client,actors):
    club=setup_club(client,actors)
    request=req(client,actors,'student','POST',f'/clubs/{club}/coordinator-requests',{'message':'I lead technical activities'},201)
    req(client,actors,'student','POST',f'/clubs/{club}/coordinator-requests',{'message':'Duplicate'},409)
    req(client,actors,'student','POST',f"/admin/coordinator-requests/{request['id']}/decision",{'status':'accepted'},403)
    req(client,actors,'admin','POST',f"/admin/coordinator-requests/{request['id']}/decision",{'status':'accepted'})
    assert req(client,actors,'student','GET','/me/memberships')[0]['role']=='coordinator'
    req(client,actors,'admin','POST',f"/admin/coordinator-requests/{request['id']}/decision",{'status':'accepted'},409)
    member=f"/clubs/{club}/members/{actors['other']['id']}"
    req(client,actors,'student','PUT',member,{'role':'coordinator'},403)
    req(client,actors,'student','PUT',member,{'role':'member'})
    req(client,actors,'student','PUT',f"/clubs/{club}/members/{actors['coordinator']['id']}",{'role':'member'},403)
    req(client,actors,'other','PUT',member,{'role':'member'},403)
    profile=req(client,actors,'outsider','GET',f"/students/{actors['other']['id']}")
    assert profile['memberships'][0]['club']['id']==club
    assert not {'email','usn','password_hash','admin','approved','active'} & profile.keys()
    assert any(x['user_id']==actors['other']['id'] for x in req(client,actors,'other','GET',f'/clubs/{club}/directory'))
    denied=req(client,actors,'outsider','POST',f'/clubs/{club}/coordinator-requests',{'message':'Request'},201)
    req(client,actors,'admin','POST',f"/admin/coordinator-requests/{denied['id']}/decision",{'status':'declined'})
    req(client,actors,'outsider','POST',f'/clubs/{club}/coordinator-requests',{'message':'Reapply with experience'},201)

def test_event_broadcast_all_active_users_once_and_read_privacy(client,actors):
    club=setup_club(client,actors)
    with SessionLocal() as db:
        db.get(User,actors['outsider']['id']).active=False; db.commit()
    event=req(client,actors,'coordinator','POST',f'/clubs/{club}/events',{'title':'Campus hack','description':'Build together','kind':'Hackathon','starts_at':FUTURE,'venue':'Hall','capacity':100},201)
    assert req(client,actors,'student','GET','/notifications')==[]
    path=f"/events/{event['id']}/moderation"
    req(client,actors,'admin','PATCH',path,{'status':'approved'})
    req(client,actors,'admin','PATCH',path,{'status':'approved'})
    for who in ['student','other','admin','coordinator']:
        notes=req(client,actors,who,'GET','/notifications')
        assert len(notes)==1 and notes[0]['resource_id']==event['id'] and not notes[0]['read']
    note=req(client,actors,'student','GET','/notifications')[0]
    req(client,actors,'other','PATCH',f"/notifications/{note['id']}/read",code=403)
    req(client,actors,'student','PATCH',f"/notifications/{note['id']}/read")
    assert req(client,actors,'student','GET','/notifications')[0]['read']
    from app.models import Notification
    with SessionLocal() as db:
        assert db.scalar(select(Notification).where(Notification.user_id==actors['outsider']['id'])) is None
    req(client,actors,'admin','POST',f'/clubs/{club}/events',{'title':'Admin event','description':'Published','kind':'Workshop','starts_at':FUTURE,'venue':'Hall','capacity':100},201)
    assert len(req(client,actors,'student','GET','/notifications'))==2
    edited={'title':'Campus hack','description':'Build together','kind':'Hackathon','starts_at':FUTURE,'venue':'New Hall','capacity':100}
    req(client,actors,'admin','PUT',f"/events/{event['id']}",edited)
    req(client,actors,'admin','PUT',f"/events/{event['id']}",edited)
    notes=req(client,actors,'student','GET','/notifications')
    assert len(notes)==3 and any('New Hall' in n['message'] for n in notes)

def test_cover_upload_authorization_validation_and_replacement(client,actors):
    club=setup_club(client,actors)
    data=BytesIO();Image.new('RGB',(100,100),'blue').save(data,format='PNG')
    body={'image':base64.b64encode(data.getvalue()).decode()}
    first=req(client,actors,'student','PUT','/me/cover',body)
    image=client.get(first['cover_url'],headers=actors['other']['headers'])
    assert image.status_code==200 and image.headers['content-type']=='image/jpeg'
    assert Image.open(BytesIO(image.content)).size==(1200,400)
    assert client.get(first['cover_url']).status_code==401
    req(client,actors,'other','PUT',f'/clubs/{club}/cover',body,403)
    req(client,actors,'coordinator','PUT',f'/clubs/{club}/cover',body)
    req(client,actors,'student','PUT','/me/cover',{'image':base64.b64encode(b'<svg></svg>').decode()},422)
    second=req(client,actors,'student','PUT','/me/cover',body)
    assert first!=second
    assert client.get(first['cover_url'],headers=actors['student']['headers']).status_code==404
    assert req(client,actors,'student','GET','/me')['cover_url']==second['cover_url']


def test_auth_ip_limit_is_configurable(client,actors,monkeypatch):
    from app.config import settings
    from app.main import app, auth_limit
    import app.main as m
    # Re-enable the real limiter with a tiny per-IP ceiling to prove it is configurable.
    app.dependency_overrides.pop(auth_limit,None)
    m._attempts.clear()
    monkeypatch.setattr(settings,'auth_ip_limit_per_minute',10)
    codes=[client.post('/v1/auth/login',json={'email':f'u{i}@example.com','password':'x'}).status_code for i in range(12)]
    assert codes[:10]==[401]*10 and codes[10]==429
    m._attempts.clear()
    monkeypatch.setattr(settings,'auth_ip_limit_per_minute',1000)
    assert client.post('/v1/auth/login',json={'email':'a@example.com','password':'x'}).status_code==401
    app.dependency_overrides[auth_limit]=lambda: None
