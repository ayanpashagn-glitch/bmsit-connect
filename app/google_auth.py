"""Verify GIS credentials using Google's maintained verifier; never decode without verification."""
from google.oauth2 import id_token
from google.auth.transport.requests import Request
from google.auth.exceptions import TransportError, GoogleAuthError
from requests import Session
from fastapi import HTTPException
from .config import settings

class BoundedRequest(Request):
    def __call__(self,*args,**kwargs):
        kwargs['timeout']=10
        return super().__call__(*args,**kwargs)

def verify_google(credential):
    if not settings.google_client_id: raise HTTPException(503,'Google sign-in is not configured')
    try:
        with Session() as session:
            claims=id_token.verify_oauth2_token(credential,BoundedRequest(session),settings.google_client_id)
    except TransportError:
        raise HTTPException(503,'Google verification unavailable; retry shortly')
    except (ValueError,GoogleAuthError,KeyError):
        raise HTTPException(401,'Invalid or expired Google credential')
    if claims.get('email_verified') is not True or not claims.get('sub') or not claims.get('email'):
        raise HTTPException(401,'Google account must have a verified email')
    email=claims['email'].lower()
    if settings.google_hosted_domain and claims.get('hd')!=settings.google_hosted_domain:
        raise HTTPException(403,'Use your college Google Workspace account')
    if settings.allowed_email_domains and email.split('@')[-1] not in settings.allowed_email_domains:
        raise HTTPException(403,'Use an approved college email domain')
    # Google is not authoritative for a third-party email without a Workspace domain.
    if not email.endswith('@gmail.com') and not claims.get('hd'):
        raise HTTPException(403,'Use email OTP registration for this third-party email account')
    return claims
