from datetime import timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from .db import get_db
from .models import User, LoginSession, now
from .config import settings

passwords = PasswordHash.recommended()
dummy_hash = passwords.hash('timing-equalization-not-an-account-password')
bearer = HTTPBearer(auto_error=False)

def digest(token):
    return sha256(token.encode()).hexdigest()

def utc(dt):
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

def issue_token(db, user):
    token = token_urlsafe(48)
    db.add(LoginSession(token_hash=digest(token), user_id=user.id,
                        expires_at=now() + timedelta(hours=settings.session_hours)))
    return token

def current_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    token = credentials.credentials if credentials else request.cookies.get('bc_session')
    if not token:
        raise HTTPException(401, 'Sign in required', headers={'WWW-Authenticate':'Bearer'})
    session = db.get(LoginSession, digest(token))
    if not session or utc(session.expires_at) <= now():
        raise HTTPException(401, 'Invalid or expired session')
    user = db.get(User, session.user_id)
    if not user or not user.active or not user.approved:
        raise HTTPException(403, 'Account access is restricted. Contact the college administrator.')
    return user

def administrator(user: User = Depends(current_user)):
    if not user.admin:
        raise HTTPException(403, 'Administrator access required')
    return user

def set_session_cookie(response,token):
    response.set_cookie('bc_session',token,httponly=True,secure=settings.cookie_secure,
                        samesite='strict',path='/',max_age=settings.session_hours*3600)
