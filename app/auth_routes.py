from datetime import timedelta
import secrets
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select, delete
from .config import settings
from .db import get_db
from .models import User, GoogleChallenge, LoginSession, PasswordReset, now
from .schemas import GoogleLogin, OTPInput, ResetPasswordInput
from .security import digest, utc, passwords, issue_token, set_session_cookie, dummy_hash
from .google_auth import verify_google
from .mail import send_password_reset

def install_auth_routes(app,auth_limit):
    @app.get('/v1/auth/options')
    def options():
        return {'google_client_id':settings.google_client_id,'email_otp_enabled':bool(settings.smtp_host and settings.smtp_from),'uploads_enabled':settings.uploads_enabled}

    @app.post('/v1/auth/google/challenge',dependencies=[Depends(auth_limit)])
    def challenge(response: Response,db=Depends(get_db)):
        if not settings.google_client_id: raise HTTPException(503,'Google sign-in is not configured')
        db.execute(delete(GoogleChallenge).where(GoogleChallenge.expires_at<now()))
        nonce=secrets.token_urlsafe(32)
        db.add(GoogleChallenge(token_hash=digest(nonce),expires_at=now()+timedelta(minutes=10)))
        db.commit()
        response.set_cookie('bc_google_nonce',nonce,httponly=True,secure=settings.cookie_secure,samesite='strict',max_age=600,path='/v1/auth/google')
        return {'nonce':nonce,'client_id':settings.google_client_id}

    @app.post('/v1/auth/google',dependencies=[Depends(auth_limit)])
    def google_login(data: GoogleLogin,request: Request,response: Response,db=Depends(get_db)):
        nonce=request.cookies.get('bc_google_nonce','')
        if not nonce: raise HTTPException(401,'Start Google sign-in again')
        claims=verify_google(data.credential)
        if not secrets.compare_digest(str(claims.get('nonce','')),nonce): raise HTTPException(401,'Google sign-in nonce mismatch')
        item=db.scalar(select(GoogleChallenge).where(GoogleChallenge.token_hash==digest(nonce)).with_for_update())
        if not item or utc(item.expires_at)<=now() or item.attempts>=5: raise HTTPException(401,'Google sign-in expired; start again')
        sub=claims['sub']; email=claims['email'].lower()
        user=db.scalar(select(User).where(User.google_sub==sub).with_for_update())
        if not user:
            user=db.scalar(select(User).where(User.email==email).with_for_update())
            if user:
                if not user.active or not user.approved: raise HTTPException(403,'Account access restricted')
                if user.google_sub and user.google_sub!=sub: raise HTTPException(409,'Account linked to another Google identity')
                # Link only after proving ownership of the existing application account.
                if not data.existing_password: return {'status':'link_required','email':email}
                item.attempts+=1
                if not passwords.verify(data.existing_password,user.password_hash):
                    db.commit(); raise HTTPException(401,'Incorrect existing account password')
                user.google_sub=sub
            else:
                if len(data.usn)<3 or not data.name: return {'status':'profile_required','email':email,'name':claims.get('name','')[:100]}
                if db.scalar(select(User.id).where(User.usn==data.usn.upper())):
                    raise HTTPException(409,'USN already registered. Sign in to that account or contact the administrator.')
                user=User(email=email,name=data.name,usn=data.usn.upper(),google_sub=sub,
                          password_hash=passwords.hash(secrets.token_urlsafe(64)),approved=True,active=True,admin=False)
                db.add(user);db.flush()
        if not user.active or not user.approved: raise HTTPException(403,'Account access restricted')
        token=issue_token(db,user)
        db.delete(item);db.commit()
        set_session_cookie(response,token)
        response.delete_cookie('bc_google_nonce',path='/v1/auth/google')
        return {'status':'signed_in'}

    @app.post('/v1/auth/forgot-password',dependencies=[Depends(auth_limit)])
    def forgot(data: OTPInput,db=Depends(get_db)):
        if not settings.smtp_host or not settings.smtp_from: raise HTTPException(503,'Password-reset email is not configured; contact the administrator')
        result={'message':'If an active account exists, a password-reset email will arrive shortly.'}
        user=db.scalar(select(User).where(User.email==str(data.email).lower()).with_for_update())
        if not user or not user.active: return result
        recent=db.scalar(select(PasswordReset).where(PasswordReset.user_id==user.id,PasswordReset.created_at>now()-timedelta(minutes=5)))
        if recent:return result
        token=secrets.token_urlsafe(32)
        for old in db.scalars(select(PasswordReset).where(PasswordReset.user_id==user.id,PasswordReset.used==False)):old.used=True
        reset_row=PasswordReset(user_id=user.id,token_hash=digest(token),expires_at=now()+timedelta(minutes=30))
        db.add(reset_row);db.commit()  # release the DB connection and row lock before slow SMTP I/O
        origin=settings.public_origin.rstrip('/') or 'http://localhost:8000'
        email=user.email
        try: send_password_reset(email,origin+'/#reset='+token)
        except Exception:
            # Same public response prevents mailbox enumeration through delivery failures.
            import logging;logging.getLogger(__name__).warning('Password-reset email delivery failed; check SMTP configuration')
            db.delete(reset_row);db.commit()
        return result

    @app.post('/v1/auth/reset-password',dependencies=[Depends(auth_limit)])
    def reset(data: ResetPasswordInput,db=Depends(get_db)):
        item=db.scalar(select(PasswordReset).where(PasswordReset.token_hash==digest(data.token)))
        if not item or item.used or utc(item.expires_at)<=now(): raise HTTPException(422,'Reset link is invalid or expired')
        user=db.scalar(select(User).where(User.id==item.user_id).with_for_update())
        item=db.scalar(select(PasswordReset).where(PasswordReset.id==item.id).with_for_update().execution_options(populate_existing=True))
        if item.used or utc(item.expires_at)<=now():raise HTTPException(422,'Reset link is invalid or expired')
        if not user.active: raise HTTPException(403,'Account access restricted')
        user.password_hash=passwords.hash(data.password);item.used=True
        db.execute(delete(LoginSession).where(LoginSession.user_id==user.id))
        for old in db.scalars(select(PasswordReset).where(PasswordReset.user_id==user.id)): old.used=True
        db.commit();return {'message':'Password updated. Sign in with your new password.'}
