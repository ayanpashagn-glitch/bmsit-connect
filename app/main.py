from collections import defaultdict, deque
from datetime import timedelta
from zoneinfo import ZoneInfo
from threading import Lock
from time import monotonic
from typing import Annotated
from fastapi import FastAPI, Depends, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, func, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import *
from .schemas import *
from .security import set_session_cookie, current_user, administrator, passwords, dummy_hash, issue_token, digest, bearer, utc

app = FastAPI(title='BMSIT Connect Backend', version='0.4.0')
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                   allow_credentials=True, allow_methods=['GET','POST','PUT','PATCH','DELETE'],
                   allow_headers=['Authorization','Content-Type','X-Campus-Request'])
DB = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(current_user)]
Admin = Annotated[User, Depends(administrator)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]

# Local fallback; REDIS_URL enables atomic shared counters for multiple workers.
_attempts = defaultdict(deque)
_attempt_lock = Lock()
async def auth_limit(request: Request):
    # Separate accounts sharing a campus NAT while retaining a coarse IP ceiling.
    ip = request.client.host if request.client else 'unknown'
    try: body=await request.json()
    except Exception: body={}
    email=str(body.get('email','')).strip().lower() if isinstance(body,dict) else ''
    nonce=request.cookies.get('bc_google_nonce','')
    key=ip+':'+digest(email or nonce) if (email or nonce) else ip
    if settings.redis_url:
        from .rate_limit import shared_auth_limit
        await shared_auth_limit(ip, key, request.url.path)
        return
    with _attempt_lock:
        t = monotonic()
        for old in list(_attempts):
            if not _attempts[old] or _attempts[old][-1] < t-60:
                del _attempts[old]
        coarse=_attempts['ip:'+ip]
        while coarse and coarse[0]<t-60: coarse.popleft()
        if len(coarse)>=settings.auth_ip_limit_per_minute: raise HTTPException(429,'Too many requests; retry in one minute')
        coarse.append(t)
        queue = _attempts[key]
        while queue and queue[0] < t-60:
            queue.popleft()
        if len(queue) >= (60 if request.url.path=='/v1/auth/google/challenge' else 10):
            raise HTTPException(429, 'Too many attempts; retry in one minute', headers={'Retry-After':'60'})
        queue.append(t)

@app.exception_handler(IntegrityError)
async def integrity_error(request, exc):
    return JSONResponse(status_code=409, content={'detail':'Duplicate record or invalid relationship'})

def get(db, model, id, lock=False):
    stmt = select(model).where(model.id == id)
    if lock:
        stmt = stmt.with_for_update()
    item = db.scalar(stmt)
    if not item:
        raise HTTPException(404, 'Record not found')
    return item

def view(item, exclude=()):
    return {c.name: (utc(getattr(item,c.name)) if isinstance(getattr(item,c.name), datetime) else getattr(item,c.name)) for c in item.__table__.columns if c.name not in exclude}

def user_view(user):
    return view(user, ('password_hash','google_sub'))

def rows(db, stmt, limit=50, offset=0):
    return [view(x) for x in db.scalars(stmt.limit(limit).offset(offset))]

def payload(data):
    result = data.model_dump()
    for key, value in result.items():
        if isinstance(value, HttpUrl):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = utc(value)
    return result

def manager(db, user, club_id):
    club = get(db, Club, club_id)
    member = db.scalar(select(Membership).where(Membership.club_id==club_id, Membership.user_id==user.id))
    if not user.admin and (not member or member.role != 'coordinator'):
        raise HTTPException(403, 'Only this club’s coordinator can perform this action')
    return club

def audit(db, user, action, id):
    db.add(Audit(actor_id=user.id, action=action, resource_id=id))

def save(db, item, user, action):
    db.add(item)
    db.flush()
    audit(db, user, action, item.id)
    db.commit()
    return view(item)

def notify(db, user_id, message, id):
    db.add(Notification(user_id=user_id, message=message, resource_id=id))

def future(value):
    if utc(value) <= now():
        raise HTTPException(422, 'Date and time must be in the future with a timezone')

def application_view(db, item, private=False):
    out = view(item, () if private else ('private_notes',))
    interview = db.scalar(select(Interview).where(Interview.application_id==item.id))
    out['interview'] = view(interview) if interview else None
    if private:
        u = db.get(User, item.user_id)
        out['applicant'] = {'id':u.id,'name':u.name,'usn':u.usn,'skills':u.skills,'branch':u.branch,'year':u.year}
    return out

def managed_application(db, user, id):
    item = get(db, Application, id, lock=True)
    recruitment = get(db, Recruitment, item.recruitment_id)
    manager(db, user, recruitment.club_id)
    return item, recruitment

def cancel_interview(db, application):
    interview = db.scalar(select(Interview).where(Interview.application_id==application.id))
    if interview:
        interview.cancelled = True

@app.get('/health')
def health():
    return {'status':'ok'}

@app.get('/ready')
def ready(db: DB):
    try:
        db.execute(select(User.id).limit(1))
    except OperationalError:
        raise HTTPException(503, 'Database unavailable or migrations missing')
    return {'status':'ready'}

@app.post('/v1/auth/register', status_code=201, dependencies=[Depends(auth_limit)])
def register(data: Signup, db: DB):
    email = str(data.email).lower()
    if settings.allowed_email_domains and email.split('@')[1] not in settings.allowed_email_domains:
        raise HTTPException(422, 'Use an approved college email domain')
    otp = db.scalar(select(EmailOTP).where(EmailOTP.email==email).with_for_update())
    if not otp or utc(otp.expires_at)<=now() or otp.attempts>=5:
        raise HTTPException(422, 'Request a new email code; the code is expired or unavailable')
    otp.attempts += 1
    if not passwords.verify(data.otp, otp.code_hash):
        db.commit()
        raise HTTPException(422, 'Incorrect code')
    user = User(email=email, usn=data.usn.upper(), name=data.name, password_hash=passwords.hash(data.password), approved=True)
    db.delete(otp)
    db.add(user)
    db.commit()
    return {'id':user.id, 'status':'active', 'message':'Email verified. You can sign in now.'}

@app.post('/v1/auth/login', dependencies=[Depends(auth_limit)])
def login(data: Login, db: DB):
    user = db.scalar(select(User).where(User.email==str(data.email).lower()))
    valid = passwords.verify(data.password, user.password_hash if user else dummy_hash)
    if not user or not valid:
        raise HTTPException(401, 'Invalid email or password')
    if not user.active or not user.approved:
        raise HTTPException(403, 'Account pending approval or disabled')
    token = issue_token(db, user)
    db.commit()
    return {'access_token':token,'token_type':'bearer','expires_in':settings.session_hours*3600}

@app.post('/v1/auth/logout', status_code=204)
def logout(request: Request, response: Response, db: DB, user: Actor, credentials=Depends(bearer)):
    session=db.get(LoginSession,digest(credentials.credentials if credentials else request.cookies.get('bc_session','')))
    if session: db.delete(session)
    response.delete_cookie('bc_session', path='/')
    db.commit()

@app.get('/v1/me')
def me(user: Actor):
    return user_view(user)

@app.put('/v1/me')
def update_profile(data: Profile, db: DB, user: Actor):
    for k,v in payload(data).items():
        setattr(user,k,v)
    save(db,user,user,'profile.updated')
    return user_view(user)

@app.get('/v1/admin/users')
def users(db: DB, user: Admin, limit: Limit=50, offset: Offset=0):
    return [user_view(u) for u in db.scalars(select(User).order_by(User.created_at.desc(),User.id).limit(limit).offset(offset))]

@app.patch('/v1/admin/users/{id}')
def access(id: str, data: UserAccess, db: DB, user: Admin):
    target = get(db,User,id,lock=True)
    if target.admin:
        raise HTTPException(409,'Admin accounts must be managed by the server operator')
    target.approved, target.active = data.approved, data.active
    # Revoke every session when approval/access is removed.
    if not target.approved or not target.active:
        for s in db.scalars(select(LoginSession).where(LoginSession.user_id==id)):
            db.delete(s)
    save(db,target,user,'account.access_changed')
    return user_view(target)

@app.get('/v1/clubs')
def clubs(db: DB, user: Actor, limit: Limit=50, offset: Offset=0):
    return rows(db,select(Club).where(Club.active==True).order_by(Club.name,Club.id),limit,offset)

@app.post('/v1/clubs', status_code=201)
def create_club(data: ClubInput, db: DB, user: Admin):
    return save(db,Club(**payload(data)),user,'club.created')

@app.put('/v1/clubs/{id}')
def update_club(id: str, data: ClubInput, db: DB, user: Actor):
    item=manager(db,user,id)
    for k,v in payload(data).items(): setattr(item,k,v)
    return save(db,item,user,'club.updated')

@app.put('/v1/clubs/{id}/members/{user_id}')
def assign_member(id: str, user_id: str, data: MemberInput, db: DB, user: Actor):
    manager(db,user,id)
    get(db,Club,id,lock=True)
    if not user.admin and data.role!='member': raise HTTPException(403,'Only administrators can assign coordinators')
    target=get(db,User,user_id)
    if not target.approved or not target.active: raise HTTPException(409,'Approve account first')
    item=db.scalar(select(Membership).where(Membership.club_id==id,Membership.user_id==user_id))
    if not item: item=Membership(club_id=id,user_id=user_id)
    if not user.admin and item.role=='coordinator': raise HTTPException(403,'Only administrators can change coordinator roles')
    item.role=data.role
    return save(db,item,user,'club.role_assigned')

@app.get('/v1/me/memberships')
def my_memberships(db: DB, user: Actor):
    return rows(db,select(Membership).where(Membership.user_id==user.id).order_by(Membership.id),100)

@app.get('/v1/clubs/{id}/members')
def members(id: str, db: DB, user: Actor, limit: Limit=50, offset: Offset=0):
    manager(db,user,id)
    return rows(db,select(Membership).where(Membership.club_id==id).order_by(Membership.id),limit,offset)

@app.post('/v1/clubs/{id}/recruitments',status_code=201)
def recruitment(id: str, data: RecruitmentInput, db: DB, user: Actor):
    manager(db,user,id)
    future(data.deadline)
    return save(db,Recruitment(club_id=id,**payload(data)),user,'recruitment.created')

@app.get('/v1/recruitments')
def recruitments(db: DB, user: Actor, limit: Limit=50, offset: Offset=0):
    return rows(db,select(Recruitment).join(Club,Club.id==Recruitment.club_id).where(Club.active==True).order_by(Recruitment.created_at.desc(),Recruitment.id),limit,offset)

@app.patch('/v1/recruitments/{id}')
def recruitment_open(id: str,data: OpenInput,db: DB,user: Actor):
    item=get(db,Recruitment,id,lock=True)
    manager(db,user,item.club_id)
    if data.open: future(item.deadline)
    item.open=data.open
    return save(db,item,user,'recruitment.availability_changed')

@app.post('/v1/recruitments/{id}/applications',status_code=201)
def apply(id: str, data: MessageInput, db: DB, user: Actor):
    item=get(db,Recruitment,id,lock=True)
    if not get(db,Club,item.club_id).active or not item.open or utc(item.deadline)<=now(): raise HTTPException(409,'Recruitment closed')
    application=Application(recruitment_id=id,user_id=user.id,message=data.message)
    db.add(application); db.flush()
    notify(db,user.id,'Application submitted: '+item.title,application.id)
    save(db,application,user,'application.submitted')
    return application_view(db,application)

@app.get('/v1/me/applications')
def my_applications(db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    return [application_view(db,a) for a in db.scalars(select(Application).where(Application.user_id==user.id).order_by(Application.created_at.desc(),Application.id).limit(limit).offset(offset))]

@app.get('/v1/recruitments/{id}/applications')
def applicants(id: str, db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    item=get(db,Recruitment,id); manager(db,user,item.club_id)
    return [application_view(db,a,True) for a in db.scalars(select(Application).where(Application.recruitment_id==id).order_by(Application.created_at,Application.id).limit(limit).offset(offset))]

@app.post('/v1/applications/{id}/withdraw')
def withdraw(id: str,db: DB,user: Actor):
    item=get(db,Application,id,lock=True)
    if item.user_id!=user.id: raise HTTPException(403,'Not your application')
    if item.status not in ['submitted','shortlisted','interview']: raise HTTPException(409,'Application already finalized')
    item.status='withdrawn'; cancel_interview(db,item)
    save(db,item,user,'application.withdrawn')
    return application_view(db,item)

@app.post('/v1/applications/{id}/decision')
def decide(id: str,data: Decision,db: DB,user: Actor):
    item, recruitment=managed_application(db,user,id)
    if item.status not in ['submitted','shortlisted','interview']: raise HTTPException(409,'Application already finalized')
    if data.status==item.status: raise HTTPException(409,'Already in this state')
    if data.status=='shortlisted' and item.status!='submitted':
        raise HTTPException(409,'Only submitted applications can be shortlisted')
    item.status=data.status; item.private_notes=data.private_notes
    if data.status in ['selected','rejected']: cancel_interview(db,item)
    if data.status=='selected':
        # Serialize membership creation across applications to different roles of one club.
        get(db,Club,recruitment.club_id,lock=True)
        member=db.scalar(select(Membership).where(Membership.club_id==recruitment.club_id,Membership.user_id==item.user_id))
        if not member: db.add(Membership(club_id=recruitment.club_id,user_id=item.user_id,role='member'))
    notify(db,item.user_id,f'{recruitment.title}: application {data.status}',item.id)
    save(db,item,user,'application.'+data.status)
    return application_view(db,item,True)

@app.put('/v1/applications/{id}/interview')
def interview(id: str,data: InterviewInput,db: DB,user: Actor):
    item,recruitment=managed_application(db,user,id)
    if item.status not in ['shortlisted','interview']: raise HTTPException(409,'Shortlist the applicant first')
    future(data.starts_at)
    record=db.scalar(select(Interview).where(Interview.application_id==id))
    if record is None: record=Interview(application_id=id); db.add(record)
    for k,v in payload(data).items(): setattr(record,k,v)
    record.cancelled=False; item.status='interview'
    notify(db,item.user_id,f'{recruitment.title}: interview scheduled for {data.starts_at.isoformat()} at {data.location}. Open your application for the link and instructions.',id)
    return save(db,record,user,'interview.scheduled_or_rescheduled')

@app.get('/v1/notifications')
def notifications(db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    return rows(db,select(Notification).where(Notification.user_id==user.id).order_by(Notification.created_at.desc(),Notification.id),limit,offset)

@app.get('/v1/notifications/summary')
def notification_summary(db: DB,user: Actor):
    return {'unread':db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id==user.id,Notification.read==False))}

@app.post('/v1/notifications/read-all')
def read_all_notifications(db: DB,user: Actor):
    from sqlalchemy import update
    db.execute(update(Notification).where(Notification.user_id==user.id,Notification.read==False).values(read=True))
    db.commit()
    return {'status':'ok'}

@app.patch('/v1/notifications/{id}/read')
def read_notification(id: str,db: DB,user: Actor):
    item=get(db,Notification,id)
    if item.user_id!=user.id: raise HTTPException(403,'Not your notification')
    item.read=True; db.commit(); return view(item)

@app.post('/v1/clubs/{id}/events',status_code=201)
def create_event(id: str,data: EventInput,db: DB,user: Actor):
    manager(db,user,id); future(data.starts_at)
    item=Event(club_id=id,status='approved' if user.admin else 'pending',**payload(data))
    db.add(item); db.flush()
    broadcast_event(db,item)
    return save(db,item,user,'event.created')

@app.get('/v1/events')
def events(db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    return rows(db,select(Event).join(Club,Club.id==Event.club_id).where(Event.status=='approved',Club.active==True).order_by(Event.starts_at,Event.id),limit,offset)

@app.get('/v1/admin/events')
def admin_events(db: DB,user: Admin,limit: Limit=50,offset: Offset=0):
    return rows(db,select(Event).order_by(Event.created_at.desc(),Event.id),limit,offset)

@app.get('/v1/clubs/{id}/events')
def club_events(id: str,db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    manager(db,user,id)
    return rows(db,select(Event).where(Event.club_id==id).order_by(Event.starts_at,Event.id),limit,offset)

@app.patch('/v1/events/{id}/moderation')
def moderate_event(id: str,data: Moderation,db: DB,user: Admin):
    item=get(db,Event,id,lock=True)
    changed=item.status!=data.status
    item.status=data.status
    if changed: broadcast_event(db,item)
    return save(db,item,user,'event.moderated')

@app.post('/v1/events/{id}/registrations',status_code=201)
def register_event(id: str,db: DB,user: Actor):
    item=get(db,Event,id,lock=True)
    if not get(db,Club,item.club_id).active or item.status!='approved' or utc(item.starts_at)<=now(): raise HTTPException(409,'Event unavailable')
    existing=db.scalar(select(Registration).where(Registration.event_id==id,Registration.user_id==user.id))
    if existing: raise HTTPException(409,'Already registered')
    count=db.scalar(select(func.count()).select_from(Registration).where(Registration.event_id==id))
    if count>=item.capacity: raise HTTPException(409,'Event full')
    return save(db,Registration(event_id=id,user_id=user.id),user,'event.registered')

@app.delete('/v1/events/{id}/registrations/me',status_code=204)
def unregister(id: str,db: DB,user: Actor):
    get(db,Event,id,lock=True)
    item=db.scalar(select(Registration).where(Registration.event_id==id,Registration.user_id==user.id))
    if item: db.delete(item); audit(db,user,'event.unregistered',id)
    db.commit()

@app.get('/v1/me/registrations')
def my_registrations(db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    return rows(db,select(Registration).where(Registration.user_id==user.id).order_by(Registration.created_at.desc(),Registration.id),limit,offset)

@app.get('/v1/events/{id}/registrations')
def event_roster(id: str,db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    item=get(db,Event,id); manager(db,user,item.club_id)
    return rows(db,select(Registration).where(Registration.event_id==id).order_by(Registration.created_at,Registration.id),limit,offset)

@app.post('/v1/clubs/{id}/announcements',status_code=201)
def announce(id: str,data: AnnouncementInput,db: DB,user: Actor):
    manager(db,user,id)
    return save(db,Announcement(club_id=id,**payload(data)),user,'announcement.created')

@app.get('/v1/announcements')
def announcements(db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    return rows(db,select(Announcement).join(Club,Club.id==Announcement.club_id).where(Club.active==True).order_by(Announcement.created_at.desc(),Announcement.id),limit,offset)

@app.post('/v1/projects',status_code=201)
def create_project(data: ProjectInput,db: DB,user: Actor):
    return save(db,Project(owner_id=user.id,**payload(data)),user,'project.created')

@app.get('/v1/projects')
def projects(db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    return rows(db,select(Project).where(Project.visible==True).order_by(Project.created_at.desc(),Project.id),limit,offset)

@app.put('/v1/projects/{id}')
def edit_project(id: str,data: ProjectInput,db: DB,user: Actor):
    item=get(db,Project,id)
    if item.owner_id!=user.id: raise HTTPException(403,'Not your project')
    for k,v in payload(data).items(): setattr(item,k,v)
    return save(db,item,user,'project.updated')

@app.patch('/v1/projects/{id}/visibility')
def project_visibility(id: str,data: Visibility,db: DB,user: Admin):
    item=get(db,Project,id); item.visible=data.visible
    return save(db,item,user,'project.moderated')

@app.post('/v1/teams',status_code=201)
def create_team(data: TeamInput,db: DB,user: Actor):
    item=Team(owner_id=user.id,**payload(data)); db.add(item); db.flush()
    db.add(TeamMember(team_id=item.id,user_id=user.id))
    return save(db,item,user,'team.created')

@app.get('/v1/teams')
def teams(db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    return rows(db,select(Team).order_by(Team.created_at.desc(),Team.id),limit,offset)

@app.patch('/v1/teams/{id}')
def team_open(id: str,data: OpenInput,db: DB,user: Actor):
    item=get(db,Team,id,lock=True)
    if item.owner_id!=user.id: raise HTTPException(403,'Not your team')
    item.open=data.open; return save(db,item,user,'team.availability_changed')

@app.post('/v1/teams/{id}/requests',status_code=201)
def request_team(id: str,data: MessageInput,db: DB,user: Actor):
    item=get(db,Team,id,lock=True)
    if not item.open or item.owner_id==user.id: raise HTTPException(409,'Team unavailable for request')
    req=TeamRequest(team_id=id,user_id=user.id,message=data.message)
    db.add(req); db.flush(); notify(db,item.owner_id,'New join request: '+item.title,req.id)
    return save(db,req,user,'team.requested')

@app.get('/v1/me/team-requests')
def my_requests(db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    return rows(db,select(TeamRequest).where(TeamRequest.user_id==user.id).order_by(TeamRequest.created_at.desc(),TeamRequest.id),limit,offset)

@app.get('/v1/teams/{id}/requests')
def team_requests(id: str,db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    item=get(db,Team,id)
    if item.owner_id!=user.id: raise HTTPException(403,'Not your team')
    return rows(db,select(TeamRequest).where(TeamRequest.team_id==id).order_by(TeamRequest.created_at,TeamRequest.id),limit,offset)

@app.post('/v1/team-requests/{id}/decision')
def team_decision(id: str,data: RequestDecision,db: DB,user: Actor):
    item=get(db,TeamRequest,id,lock=True); team=get(db,Team,item.team_id,lock=True)
    if team.owner_id!=user.id: raise HTTPException(403,'Not your team')
    if item.status!='pending': raise HTTPException(409,'Request already decided')
    if data.status=='accepted' and not team.open: raise HTTPException(409,'Reopen the team before accepting requests')
    item.status=data.status
    if data.status=='accepted': db.add(TeamMember(team_id=team.id,user_id=item.user_id))
    notify(db,item.user_id,f'{team.title}: join request {data.status}',item.id)
    return save(db,item,user,'team.request_'+data.status)

@app.get('/v1/teams/{id}/members')
def team_members(id: str,db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    get(db,Team,id)
    member=db.scalar(select(TeamMember).where(TeamMember.team_id==id,TeamMember.user_id==user.id))
    if not member and not user.admin: raise HTTPException(403,'Team members only')
    return rows(db,select(TeamMember).where(TeamMember.team_id==id).order_by(TeamMember.id),limit,offset)

@app.get('/v1/admin/audit')
def audit_log(db: DB,user: Admin,limit: Limit=50,offset: Offset=0):
    return rows(db,select(Audit).order_by(Audit.created_at.desc(),Audit.id),limit,offset)

@app.get('/v1/students')
def students(db: DB,user: Actor,limit: Limit=50,offset: Offset=0, q: Annotated[str,Query(max_length=100)]=''):
    stmt=select(User).where(User.active==True,User.approved==True,User.admin==False)
    if q:
        stmt=stmt.where(User.name.contains(q,autoescape=True) | User.skills.contains(q,autoescape=True))
    return [{k:getattr(u,k) for k in ['id','name','branch','year','skills','bio','github','cover_url']}
            for u in db.scalars(stmt.order_by(User.name,User.id).limit(limit).offset(offset))]

@app.get('/v1/people')
def people(db: DB,user: Actor,ids: Annotated[str,Query(max_length=3700)]=''):
    keys=list(dict.fromkeys(x for x in ids.split(',') if x))
    if len(keys)>100:raise HTTPException(422,'Request at most 100 names')
    return [{'id':u.id,'name':u.name} for u in db.scalars(select(User).where(User.id.in_(keys),User.active==True,User.approved==True,User.admin==False))]

@app.get('/v1/students/{id}')
def student_profile(id: str,db: DB,user: Actor):
    target=get(db,User,id)
    if not target.active or not target.approved or target.admin: raise HTTPException(404,'Student not found')
    result={k:getattr(target,k) for k in ['id','name','branch','year','skills','bio','github','cover_url']}
    result['memberships']=[{'club':view(c),'role':m.role} for m,c in db.execute(select(Membership,Club).join(Club,Club.id==Membership.club_id).where(Membership.user_id==id,Club.active==True))]
    result['projects']=rows(db,select(Project).where(Project.owner_id==id,Project.visible==True).order_by(Project.created_at.desc()),100)
    return result

@app.put('/v1/clubs/{id}/follow')
def follow(id: str,db: DB,user: Actor):
    if not get(db,Club,id,lock=True).active: raise HTTPException(404,'Club not found')
    item=db.scalar(select(Follow).where(Follow.club_id==id,Follow.user_id==user.id))
    if item: return view(item)
    return save(db,Follow(club_id=id,user_id=user.id),user,'club.followed')

@app.delete('/v1/clubs/{id}/follow',status_code=204)
def unfollow(id: str,db: DB,user: Actor):
    get(db,Club,id,lock=True)
    item=db.scalar(select(Follow).where(Follow.club_id==id,Follow.user_id==user.id))
    if item: db.delete(item)
    db.commit()

@app.get('/v1/me/follows')
def follows(db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    return rows(db,select(Follow).where(Follow.user_id==user.id).order_by(Follow.id),limit,offset)

@app.put('/v1/projects/{id}/save')
def save_project(id: str,db: DB,user: Actor):
    project=get(db,Project,id,lock=True)
    if not project.visible: raise HTTPException(404,'Project not found')
    item=db.scalar(select(SavedProject).where(SavedProject.project_id==id,SavedProject.user_id==user.id))
    if item: return view(item)
    return save(db,SavedProject(project_id=id,user_id=user.id),user,'project.saved')

@app.delete('/v1/projects/{id}/save',status_code=204)
def unsave_project(id: str,db: DB,user: Actor):
    get(db,Project,id,lock=True)
    item=db.scalar(select(SavedProject).where(SavedProject.project_id==id,SavedProject.user_id==user.id))
    if item: db.delete(item)
    db.commit()

@app.get('/v1/me/saved-projects')
def saved_projects(db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    return rows(db,select(Project).join(SavedProject,SavedProject.project_id==Project.id).where(SavedProject.user_id==user.id,Project.visible==True).order_by(Project.id),limit,offset)

@app.middleware('http')
async def browser_security(request: Request, call_next):
    # Cookie writes and web-login must originate from the app, not an external form.
    if request.method not in ['GET','HEAD','OPTIONS'] and request.url.path.startswith('/v1/'):
        cookie_write = request.cookies.get('bc_session') and not request.headers.get('authorization','').lower().startswith('bearer ')
        if cookie_write or request.url.path in ['/v1/auth/web-login','/v1/auth/google/challenge','/v1/auth/google','/v1/auth/forgot-password','/v1/auth/reset-password']:
            expected = settings.public_origin.rstrip('/') or str(request.base_url).rstrip('/')
            if request.headers.get('origin') not in [expected, *settings.cors_origins] or request.headers.get('x-campus-request') != '1':
                return JSONResponse(status_code=403,content={'detail':'Invalid browser request origin'})
    if request.url.path.startswith('/v1/') and request.method in ['POST','PUT','PATCH']:
        total=0; parts=[]
        async for chunk in request.stream():
            total+=len(chunk)
            if total>3_000_000: return JSONResponse(status_code=413,content={'detail':'Request exceeds 3 MB limit'})
            parts.append(chunk)
        request._body=b''.join(parts)
    response = await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    response.headers['X-Frame-Options']='DENY'
    if request.url.path.startswith('/v1/covers/') and response.status_code==200:
        response.headers['Cache-Control']='private, max-age=300'  # ids are immutable per upload
    elif request.url.path.startswith('/v1/'):
        response.headers['Cache-Control']='no-store'
    return response

@app.post('/v1/auth/web-login', dependencies=[Depends(auth_limit)])
def web_login(data: Login, response: Response, db: DB):
    result=login(data,db)
    set_session_cookie(response,result['access_token'])
    return {'status':'signed_in'}

@app.get('/v1/admin/clubs')
def admin_clubs(db: DB,user: Admin,limit: Limit=50,offset: Offset=0):
    return rows(db,select(Club).order_by(Club.name,Club.id),limit,offset)

@app.patch('/v1/clubs/{id}/visibility')
def club_visibility(id: str,data: Visibility,db: DB,user: Admin):
    item=get(db,Club,id,lock=True);item.active=data.visible
    return save(db,item,user,'club.visibility_changed')

@app.get('/v1/admin/projects')
def admin_projects(db: DB,user: Admin,limit: Limit=50,offset: Offset=0):
    return rows(db,select(Project).order_by(Project.created_at.desc(),Project.id),limit,offset)

@app.get('/v1/me/projects')
def own_projects(db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    return rows(db,select(Project).where(Project.owner_id==user.id).order_by(Project.created_at.desc(),Project.id),limit,offset)

@app.get('/v1/me/events')
def own_events(db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    return rows(db,select(Event).join(Registration,Registration.event_id==Event.id).where(Registration.user_id==user.id).order_by(Event.starts_at,Event.id),limit,offset)

@app.get('/v1/clubs/{id}/recruitments')
def club_recruitments(id: str,db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    manager(db,user,id)
    return rows(db,select(Recruitment).where(Recruitment.club_id==id).order_by(Recruitment.created_at.desc(),Recruitment.id),limit,offset)

@app.put('/v1/recruitments/{id}')
def edit_recruitment(id: str,data: RecruitmentInput,db: DB,user: Actor):
    item=get(db,Recruitment,id,lock=True);manager(db,user,item.club_id);future(data.deadline)
    for k,v in payload(data).items():setattr(item,k,v)
    return save(db,item,user,'recruitment.updated')

@app.put('/v1/events/{id}')
def edit_event(id: str,data: EventInput,db: DB,user: Actor):
    item=get(db,Event,id,lock=True);manager(db,user,item.club_id);future(data.starts_at)
    count=db.scalar(select(func.count()).select_from(Registration).where(Registration.event_id==id))
    if data.capacity<count:raise HTTPException(409,'Capacity cannot be lower than existing registrations')
    changed=any((utc(getattr(item,k)) if isinstance(getattr(item,k),datetime) else getattr(item,k))!=v for k,v in payload(data).items())
    for k,v in payload(data).items():setattr(item,k,v)
    if not user.admin:item.status='pending'
    elif changed: broadcast_event(db,item)
    return save(db,item,user,'event.updated')

@app.put('/v1/teams/{id}')
def edit_team(id: str,data: TeamInput,db: DB,user: Actor):
    item=get(db,Team,id,lock=True)
    if item.owner_id!=user.id:raise HTTPException(403,'Not your team')
    for k,v in payload(data).items():setattr(item,k,v)
    return save(db,item,user,'team.updated')

# The release ZIP contains the compiled UI. No separate frontend server is needed.
from pathlib import Path

import secrets
import base64
from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError
from .mail import send_otp

def broadcast_event(db, event):
    if event.status!='approved' or not get(db,Club,event.club_id).active: return
    message=f'Campus event: {event.title} · {utc(event.starts_at).astimezone(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y, %I:%M %p IST")} · {event.venue}'
    from sqlalchemy import insert
    ids=list(db.scalars(select(User.id).where(User.active==True,User.approved==True)))
    if ids: db.execute(insert(Notification),[{'user_id':i,'message':message,'resource_id':event.id} for i in ids])

@app.post('/v1/auth/request-otp', dependencies=[Depends(auth_limit)])
def request_otp(data: OTPInput, db: DB):
    email=str(data.email).lower()
    if settings.allowed_email_domains and email.split('@')[1] not in settings.allowed_email_domains:
        raise HTTPException(422,'Use an approved college email domain')
    if db.scalar(select(User.id).where(User.email==email)):
        raise HTTPException(409,'This email is already registered; sign in instead')
    item=db.scalar(select(EmailOTP).where(EmailOTP.email==email).with_for_update())
    if item and utc(item.sent_at)>now()-timedelta(seconds=60):
        raise HTTPException(429,'Wait 60 seconds before requesting another code')
    code=f'{secrets.randbelow(1000000):06d}'
    if not item: item=EmailOTP(email=email)
    item.code_hash=passwords.hash(code); item.sent_at=now(); item.expires_at=now()+timedelta(minutes=10); item.attempts=0
    db.add(item); db.commit()  # release the DB connection and row lock before slow SMTP I/O
    try: send_otp(email,code)
    except Exception:
        db.delete(item); db.commit()  # drop the undelivered code so the student can retry immediately
        raise HTTPException(503,'Email could not be sent. Ask the administrator to check SMTP settings, then retry.')
    return {'message':'Code sent. Check your inbox and spam folder. It expires in 10 minutes.'}

@app.post('/v1/clubs/{id}/coordinator-requests', status_code=201)
def request_coordinator(id: str, data: MessageInput, db: DB, user: Actor):
    club=get(db,Club,id,lock=True)
    if not club.active: raise HTTPException(404,'Club not found')
    membership=db.scalar(select(Membership).where(Membership.club_id==id,Membership.user_id==user.id))
    if user.admin or (membership and membership.role=='coordinator'): raise HTTPException(409,'You already manage this club')
    item=db.scalar(select(CoordinatorRequest).where(CoordinatorRequest.club_id==id,CoordinatorRequest.user_id==user.id))
    if item and item.status!='declined': raise HTTPException(409,'A request already exists')
    if not item: item=CoordinatorRequest(club_id=id,user_id=user.id)
    item.message=data.message; item.status='pending'
    db.add(item); db.flush()
    for admin_id in db.scalars(select(User.id).where(User.admin==True,User.active==True)):
        notify(db,admin_id,f'{user.name} requested coordinator access to {club.name}',item.id)
    return save(db,item,user,'coordinator.requested')

@app.get('/v1/me/coordinator-requests')
def own_coordinator_requests(db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    return rows(db,select(CoordinatorRequest).where(CoordinatorRequest.user_id==user.id).order_by(CoordinatorRequest.created_at.desc(),CoordinatorRequest.id),limit,offset)

@app.get('/v1/admin/coordinator-requests')
def coordinator_requests(db: DB,user: Admin,limit: Limit=50,offset: Offset=0):
    return rows(db,select(CoordinatorRequest).order_by(CoordinatorRequest.created_at.desc(),CoordinatorRequest.id),limit,offset)

@app.post('/v1/admin/coordinator-requests/{id}/decision')
def coordinator_decision(id: str,data: RequestDecision,db: DB,user: Admin):
    item=get(db,CoordinatorRequest,id,lock=True)
    if item.status!='pending': raise HTTPException(409,'Request already reviewed')
    target=get(db,User,item.user_id)
    club=get(db,Club,item.club_id,lock=True)
    if data.status=='accepted':
        if not target.active or not target.approved or not club.active: raise HTTPException(409,'Student and club must be active')
        member=db.scalar(select(Membership).where(Membership.club_id==item.club_id,Membership.user_id==item.user_id))
        if not member: member=Membership(club_id=item.club_id,user_id=item.user_id)
        member.role='coordinator'; db.add(member)
    item.status=data.status
    notify(db,item.user_id,f'Coordinator request {item.status}: {club.name}',item.id)
    return save(db,item,user,'coordinator.reviewed')

@app.get('/v1/clubs/{id}/directory')
def club_directory(id: str,db: DB,user: Actor,limit: Limit=50,offset: Offset=0):
    club=get(db,Club,id)
    if not club.active: raise HTTPException(404,'Club not found')
    return [{'id':m.id,'role':m.role,'user_id':u.id,'name':u.name} for m,u in db.execute(select(Membership,User).join(User,User.id==Membership.user_id).where(Membership.club_id==id,User.active==True,User.approved==True,User.admin==False).order_by(User.name,User.id).limit(limit).offset(offset))]

def store_cover(db, target, data, user):
    if not settings.uploads_enabled: raise HTTPException(403, 'Image uploads are disabled for this campus')
    try:
        raw=base64.b64decode(data.image,validate=True)
        if len(raw)>settings.cover_max_bytes: raise ValueError()
        with Image.open(BytesIO(raw)) as img:
            if img.format not in ('PNG','JPEG','WEBP') or img.width*img.height>16_000_000: raise ValueError()
            img=ImageOps.exif_transpose(img).convert('RGB')
            img=ImageOps.fit(img,(1200,400))
            output=BytesIO(); img.save(output,format='JPEG',quality=85)
        content=output.getvalue()
    except (ValueError,UnidentifiedImageError,OSError,Image.DecompressionBombError):
        raise HTTPException(422,'Choose a valid JPEG, PNG or WebP image under 2 MB and 16 megapixels')
    # Lock and refresh the owner so concurrent uploads cannot orphan its prior cover.
    target=db.scalar(select(type(target)).where(type(target).id==target.id).with_for_update().execution_options(populate_existing=True))
    cover=CoverImage(id=uid(),storage_backend=settings.storage_backend,size_bytes=len(content))
    cover.storage_key=cover.id+'.jpg'
    from .storage import put_image, delete_image, drain_deletions, StorageError
    try: put_image(cover.storage_backend,cover.storage_key,content)
    except StorageError: raise HTTPException(503,'Image storage unavailable. Ask the administrator to check storage settings.')
    try:
        db.add(cover)
        old=target.cover_url
        target.cover_url='/v1/covers/'+cover.id
        if old:
            previous=db.get(CoverImage,old.rsplit('/',1)[-1])
            if previous:
                if previous.storage_key: db.add(StorageDeletion(storage_backend=previous.storage_backend,storage_key=previous.storage_key))
                db.delete(previous)
        save(db,target,user,'cover.updated')
    except Exception:
        db.rollback()
        try: delete_image(cover.storage_backend,cover.storage_key)
        except StorageError:
            db.add(StorageDeletion(storage_backend=cover.storage_backend,storage_key=cover.storage_key)); db.commit()
        raise
    drain_deletions(db,limit=5)
    return {'cover_url':target.cover_url}

@app.put('/v1/me/cover')
def student_cover(data: CoverInput,db: DB,user: Actor):
    return store_cover(db,user,data,user)

@app.put('/v1/clubs/{id}/cover')
def club_cover(id: str,data: CoverInput,db: DB,user: Actor):
    return store_cover(db,manager(db,user,id),data,user)

@app.get('/v1/covers/{id}')
def cover_image(id: str,db: DB,user: Actor):
    item=get(db,CoverImage,id)
    if item.storage_backend=='database': content=item.content
    else:
        from .storage import read_image, StorageError
        try: content=read_image(item.storage_backend,item.storage_key)
        except StorageError: raise HTTPException(503,'Image storage temporarily unavailable')
    return Response(content,media_type='image/jpeg')

from .auth_routes import install_auth_routes
install_auth_routes(app,auth_limit)

from fastapi.staticfiles import StaticFiles
web_dir=Path(__file__).resolve().parent.parent/'web'
if web_dir.is_dir():
    app.mount('/',StaticFiles(directory=web_dir,html=True),name='frontend')
