from datetime import timedelta
from app.models import now
from .test_workflows import req,setup_club,setup_application,FUTURE

def web_headers():return {'Origin':'http://testserver','X-Campus-Request':'1'}

def test_web_cookie_login_reload_logout_and_csrf(client,actors):
    login={'email':'student@example.com','password':'secure-test-pass-123'}
    assert client.post('/v1/auth/web-login',json=login).status_code==403
    response=client.post('/v1/auth/web-login',json=login,headers=web_headers())
    assert response.status_code==200
    assert 'access_token' not in response.json()
    assert 'HttpOnly' in response.headers['set-cookie'] and 'SameSite=strict' in response.headers['set-cookie']
    assert client.get('/v1/me').json()['id']==actors['student']['id']
    payload={'title':'My project','category':'AI / ML','description':'Real data','skills':'Python'}
    assert client.post('/v1/projects',json=payload,headers={'Origin':'https://other.example','X-Campus-Request':'1'}).status_code==403
    assert client.post('/v1/projects',json=payload,headers={'Authorization':'Basic ignored','Origin':'https://other.example'}).status_code==403
    assert client.post('/v1/projects',json=payload,headers=web_headers()).status_code==201
    assert client.get('/v1/me/projects').json()[0]['category']=='AI / ML'
    assert client.post('/v1/auth/logout',headers=web_headers()).status_code==204
    assert not client.cookies.get('bc_session')
    assert client.get('/v1/me').status_code==401

def test_admin_hidden_club_and_moderation_lists(client,actors):
    club,opening,_=setup_application(client,actors)
    req(client,actors,'student','GET','/admin/clubs',code=403)
    req(client,actors,'admin','PATCH',f'/clubs/{club}/visibility',{'visible':False})
    assert req(client,actors,'student','GET','/clubs')==[]
    assert req(client,actors,'student','GET','/recruitments')==[]
    req(client,actors,'other','POST',f'/recruitments/{opening}/applications',{'message':'Try hidden opening'},409)
    assert len(req(client,actors,'admin','GET','/admin/clubs'))==1
    p=req(client,actors,'student','POST','/projects',{'title':'Test','category':'Hardware','description':'Description','skills':'C'},201)
    req(client,actors,'admin','PATCH',f"/projects/{p['id']}/visibility",{'visible':False})
    assert len(req(client,actors,'student','GET','/me/projects'))==1
    assert len(req(client,actors,'admin','GET','/admin/projects'))==1

def test_event_edits_return_to_approval_and_keep_capacity(client,actors):
    club=setup_club(client,actors)
    payload={'title':'Event','kind':'Hackathon','description':'Details','starts_at':FUTURE,'venue':'Lab','capacity':2}
    event=req(client,actors,'coordinator','POST',f'/clubs/{club}/events',payload,201)
    id=event['id']
    req(client,actors,'admin','PATCH',f'/events/{id}/moderation',{'status':'approved'})
    req(client,actors,'student','POST',f'/events/{id}/registrations',code=201)
    req(client,actors,'other','POST',f'/events/{id}/registrations',code=201)
    req(client,actors,'coordinator','PUT',f'/events/{id}',{**payload,'capacity':1},409)
    updated=req(client,actors,'coordinator','PUT',f'/events/{id}',{**payload,'venue':'New lab'})
    assert updated['status']=='pending'
    assert req(client,actors,'student','GET','/me/events')[0]['venue']=='New lab'

def test_frontend_is_served_without_exposing_source(client):
    response=client.get('/')
    assert response.status_code==200 and '<div id="root">' in response.text
    assert client.get('/.env').status_code==404
    assert client.get('/app/config.py').status_code==404

def test_interview_timezone_is_normalized(client,actors):
    _,_,id=setup_application(client,actors)
    req(client,actors,'coordinator','POST',f'/applications/{id}/decision',{'status':'shortlisted'})
    result=req(client,actors,'coordinator','PUT',f'/applications/{id}/interview',{'starts_at':'2030-10-02T14:00:00+05:30','location':'Room 101'})
    assert result['starts_at']=='2030-10-02T08:30:00+00:00'
    own=req(client,actors,'student','GET','/me/applications')[0]
    assert own['interview']['starts_at']=='2030-10-02T08:30:00+00:00'
