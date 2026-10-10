from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from sqlalchemy import select, func
import pytest
from app.models import *
from app.db import SessionLocal, engine
from app.main import app, auth_limit, _attempts
from app.security import passwords

FUTURE=(now()+timedelta(days=30)).isoformat()

def req(client, actors, who, method, path, data=None, code=200):
    response=client.request(method,'/v1'+path,headers=actors[who]['headers'],json=data)
    assert response.status_code==code,response.text
    return response.json() if response.content else None

def setup_club(c,a,name='ASTRA'):
    club=req(c,a,'admin','POST','/clubs',{'name':name,'category':'Technology','description':'Student club'},201)
    req(c,a,'admin','PUT',f"/clubs/{club['id']}/members/{a['coordinator']['id']}",{'role':'coordinator'})
    return club['id']

def setup_application(c,a):
    club=setup_club(c,a)
    opening=req(c,a,'coordinator','POST',f'/clubs/{club}/recruitments',{'title':'Technical recruitment','role':'Technical','description':'Join our team','deadline':FUTURE},201)
    application=req(c,a,'student','POST',f"/recruitments/{opening['id']}/applications",{'message':'I build Python projects'},201)
    return club,opening['id'],application['id']

def test_verified_account_login_logout_and_no_escalation(client,actors,monkeypatch):
    codes=[]
    monkeypatch.setattr("app.main.send_otp",lambda email,code: codes.append(code))
    assert client.post("/v1/auth/request-otp",json={"email":"new@example.com"}).status_code==200
    data={'name':'New student','usn':'1TE25CS999','email':'new@example.com','password':'strong-test-pass-123','otp':codes[0]}
    response=client.post('/v1/auth/register',json={**data,'admin':True})
    assert response.status_code==422
    user=client.post('/v1/auth/register',json=data)
    assert user.status_code==201
    login={'email':data['email'],'password':data['password']}
    assert client.post('/v1/auth/login',json=login).status_code==200
    req(client,actors,'student','PATCH',f"/admin/users/{user.json()['id']}",{'approved':True,'active':True},403)
    response=client.post('/v1/auth/login',json=login)
    assert response.status_code==200
    headers={'Authorization':'Bearer '+response.json()['access_token']}
    profile=client.get('/v1/me',headers=headers).json()
    assert profile['admin'] is False and 'password_hash' not in profile
    assert client.post('/v1/auth/logout',headers=headers).status_code==204
    assert client.get('/v1/me',headers=headers).status_code==401
    assert client.get('/v1/clubs').status_code==401

def test_recruitment_interview_selection_and_privacy(client,actors):
    club,opening,application=setup_application(client,actors)
    req(client,actors,'student','POST',f'/recruitments/{opening}/applications',{'message':'duplicate'},409)
    req(client,actors,'outsider','GET',f'/recruitments/{opening}/applications',code=403)
    req(client,actors,'student','POST',f'/applications/{application}/decision',{'status':'selected'},403)
    req(client,actors,'coordinator','POST',f'/applications/{application}/decision',{'status':'shortlisted','private_notes':'Private interview rubric'})
    body={'starts_at':FUTURE,'location':'Seminar hall','meeting_url':'https://example.com/meeting','instructions':'Bring your portfolio'}
    first=req(client,actors,'coordinator','PUT',f'/applications/{application}/interview',body)
    second=req(client,actors,'coordinator','PUT',f'/applications/{application}/interview',{**body,'location':'Room 2'})
    assert first['id']==second['id']
    req(client,actors,'coordinator','POST',f'/applications/{application}/decision',{'status':'shortlisted'},409)
    student_view=req(client,actors,'student','GET','/me/applications')[0]
    assert 'private_notes' not in student_view
    assert student_view['interview']['location']=='Room 2'
    req(client,actors,'coordinator','POST',f'/applications/{application}/decision',{'status':'selected'})
    member=req(client,actors,'student','GET','/me/memberships')
    assert len(member)==1 and member[0]['club_id']==club
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Interview))==1
        assert db.scalar(select(Interview)).cancelled
    req(client,actors,'coordinator','POST',f'/applications/{application}/decision',{'status':'selected'},409)
    notifications=req(client,actors,'student','GET','/notifications')
    assert any('selected' in x['message'] for x in notifications)
    req(client,actors,'other','PATCH',f"/notifications/{notifications[0]['id']}/read",code=403)
    req(client,actors,'student','PATCH',f"/notifications/{notifications[0]['id']}/read")

def test_coordinator_is_scoped_to_assigned_club(client,actors):
    setup_club(client,actors)
    club=req(client,actors,'admin','POST','/clubs',{'name':'Another club','category':'Art','description':'Arts'},201)
    req(client,actors,'coordinator','POST',f"/clubs/{club['id']}/recruitments",{'title':'Test','role':'Design','description':'Join','deadline':FUTURE},403)
    req(client,actors,'coordinator','PUT',f"/clubs/{club['id']}/members/{actors['coordinator']['id']}",{'role':'coordinator'},403)

def test_withdrawal_closes_interview_and_prevents_decision(client,actors):
    club,opening,application=setup_application(client,actors)
    req(client,actors,'coordinator','POST',f'/applications/{application}/decision',{'status':'shortlisted'})
    req(client,actors,'coordinator','PUT',f'/applications/{application}/interview',{'starts_at':FUTURE,'location':'Room 1'})
    req(client,actors,'other','POST',f'/applications/{application}/withdraw',code=403)
    req(client,actors,'student','POST',f'/applications/{application}/withdraw')
    req(client,actors,'coordinator','POST',f'/applications/{application}/decision',{'status':'selected'},409)
    assert req(client,actors,'student','GET','/me/applications')[0]['interview']['cancelled']

def test_closed_and_expired_recruitment(client,actors):
    _,opening,_=setup_application(client,actors)
    req(client,actors,'coordinator','PATCH',f'/recruitments/{opening}',{'open':False})
    req(client,actors,'other','POST',f'/recruitments/{opening}/applications',{'message':'Join'},409)
    with SessionLocal() as db:
        r=db.get(Recruitment,opening); r.open=True; r.deadline=now()-timedelta(days=1); db.commit()
    req(client,actors,'other','POST',f'/recruitments/{opening}/applications',{'message':'Join'},409)

def setup_event(c,a):
    club=setup_club(c,a)
    event=req(c,a,'coordinator','POST',f'/clubs/{club}/events',{'title':'Hackathon','description':'Build together','kind':'Hackathon','starts_at':FUTURE,'venue':'Lab','capacity':1},201)
    return event['id']

def test_events_require_approval_and_enforce_capacity(client,actors):
    id=setup_event(client,actors)
    assert req(client,actors,'student','GET','/events')==[]
    req(client,actors,'student','POST',f'/events/{id}/registrations',code=409)
    req(client,actors,'coordinator','PATCH',f'/events/{id}/moderation',{'status':'approved'},403)
    req(client,actors,'admin','PATCH',f'/events/{id}/moderation',{'status':'approved'})
    req(client,actors,'student','POST',f'/events/{id}/registrations',code=201)
    req(client,actors,'student','POST',f'/events/{id}/registrations',code=409)
    req(client,actors,'other','POST',f'/events/{id}/registrations',code=409)
    req(client,actors,'student','GET',f'/events/{id}/registrations',code=403)
    req(client,actors,'student','DELETE',f'/events/{id}/registrations/me',code=204)
    req(client,actors,'other','POST',f'/events/{id}/registrations',code=201)

@pytest.mark.skipif(engine.dialect.name!='postgresql',reason='Requires PostgreSQL row locking')
def test_concurrent_registration_last_seat(client,actors):
    id=setup_event(client,actors)
    req(client,actors,'admin','PATCH',f'/events/{id}/moderation',{'status':'approved'})
    def register(who):
        return client.post(f'/v1/events/{id}/registrations',headers=actors[who]['headers']).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes=list(pool.map(register,['student','other']))
    assert sorted(codes)==[201,409]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Registration))==1

def test_project_ownership_and_moderation(client,actors):
    body={'title':'Campus map','description':'Find classrooms','skills':'Python','link':'https://example.com'}
    project=req(client,actors,'student','POST','/projects',body,201)
    req(client,actors,'other','PUT',f"/projects/{project['id']}",body,403)
    req(client,actors,'student','PUT',f"/projects/{project['id']}",{**body,'link':'javascript:alert(1)'},422)
    req(client,actors,'admin','PATCH',f"/projects/{project['id']}/visibility",{'visible':False})
    req(client,actors,'student','PUT',f"/projects/{project['id']}",{**body,'description':'Updated'})
    assert req(client,actors,'other','GET','/projects')==[]

def test_team_request_permissions_membership_and_duplicates(client,actors):
    team=req(client,actors,'student','POST','/teams',{'title':'Hackathon crew','description':'Build tools','skills':'Python','commitment':'Weekends'},201)
    id=team['id']
    req(client,actors,'student','POST',f'/teams/{id}/requests',{'message':'Self'},409)
    request=req(client,actors,'other','POST',f'/teams/{id}/requests',{'message':'I can help'},201)
    req(client,actors,'other','POST',f'/teams/{id}/requests',{'message':'Again'},409)
    req(client,actors,'outsider','GET',f'/teams/{id}/requests',code=403)
    req(client,actors,'outsider','POST',f"/team-requests/{request['id']}/decision",{'status':'accepted'},403)
    req(client,actors,'student','POST',f"/team-requests/{request['id']}/decision",{'status':'accepted'})
    req(client,actors,'student','POST',f"/team-requests/{request['id']}/decision",{'status':'accepted'},409)
    assert len(req(client,actors,'other','GET',f'/teams/{id}/members'))==2
    req(client,actors,'student','PATCH',f'/teams/{id}',{'open':False})
    req(client,actors,'outsider','POST',f'/teams/{id}/requests',{'message':'Join'},409)

def test_disable_revokes_tokens_and_reenable_does_not_restore(client,actors):
    id=actors['student']['id']
    req(client,actors,'admin','PATCH',f'/admin/users/{id}',{'approved':True,'active':False})
    req(client,actors,'student','GET','/me',code=401)
    req(client,actors,'admin','PATCH',f'/admin/users/{id}',{'approved':True,'active':True})
    req(client,actors,'student','GET','/me',code=401)

def test_expired_session(client,actors):
    with SessionLocal() as db:
        session=db.scalar(select(LoginSession).where(LoginSession.user_id==actors['student']['id']))
        session.expires_at=now()-timedelta(seconds=1); db.commit()
    req(client,actors,'student','GET','/me',code=401)

def test_invalid_dates_extra_fields_and_pagination(client,actors):
    club=setup_club(client,actors)
    body={'title':'Recruit','role':'Tech','description':'Hello','deadline':'2030-01-01T12:00:00'}
    req(client,actors,'coordinator','POST',f'/clubs/{club}/recruitments',body,422)
    req(client,actors,'student','GET','/clubs?limit=1000',code=422)
    req(client,actors,'student','PUT','/me',{'name':'Name','branch':'CSE','year':2,'admin':True},422)

def test_audit_announcements_and_ready(client,actors):
    club=setup_club(client,actors)
    req(client,actors,'coordinator','POST',f'/clubs/{club}/announcements',{'title':'Welcome','body':'Recruitment opens soon'},201)
    assert len(req(client,actors,'student','GET','/announcements'))==1
    req(client,actors,'student','GET','/admin/audit',code=403)
    audit=req(client,actors,'admin','GET','/admin/audit')
    assert any(x['action']=='announcement.created' for x in audit)
    assert client.get('/ready').status_code==200

def test_auth_rate_limit(client):
    app.dependency_overrides.pop(auth_limit,None)
    _attempts.clear()
    for _ in range(10):
        assert client.post('/v1/auth/login',json={'email':'missing@example.com','password':'wrong'}).status_code==401
    response=client.post('/v1/auth/login',json={'email':'missing@example.com','password':'wrong'})
    assert response.status_code==429 and response.headers['Retry-After']=='60'
    _attempts.clear()

def test_follows_bookmarks_and_student_directory_privacy(client,actors):
    club=setup_club(client,actors)
    first=req(client,actors,'student','PUT',f'/clubs/{club}/follow')
    second=req(client,actors,'student','PUT',f'/clubs/{club}/follow')
    assert first['id']==second['id']
    assert len(req(client,actors,'student','GET','/me/follows'))==1
    req(client,actors,'student','DELETE',f'/clubs/{club}/follow',code=204)
    assert req(client,actors,'student','GET','/me/follows')==[]
    project=req(client,actors,'other','POST','/projects',{'title':'Test','description':'Test','skills':'Python'},201)
    req(client,actors,'student','PUT',f"/projects/{project['id']}/save")
    req(client,actors,'student','PUT',f"/projects/{project['id']}/save")
    assert len(req(client,actors,'student','GET','/me/saved-projects'))==1
    req(client,actors,'admin','PATCH',f"/projects/{project['id']}/visibility",{'visible':False})
    assert req(client,actors,'student','GET','/me/saved-projects')==[]
    for profile in req(client,actors,'student','GET','/students'):
        assert not {'email','usn','password_hash','approved','admin'} & profile.keys()

def test_selection_transaction_rolls_back_on_notification_failure(client,actors,monkeypatch):
    import app.main as routes
    _,_,id=setup_application(client,actors)
    def failed(*args): raise RuntimeError('Simulated notification insert failure')
    monkeypatch.setattr(routes,'notify',failed)
    with pytest.raises(RuntimeError):
        client.post(f'/v1/applications/{id}/decision',headers=actors['coordinator']['headers'],json={'status':'selected'})
    with SessionLocal() as db:
        assert db.get(Application,id).status=='submitted'
        assert db.scalar(select(Membership).where(Membership.user_id==actors['student']['id'])) is None

def test_data_persists_across_new_client(client,actors):
    from fastapi.testclient import TestClient
    setup_club(client,actors)
    with TestClient(app) as second:
        assert req(second,actors,'student','GET','/clubs')[0]['name']=='ASTRA'
