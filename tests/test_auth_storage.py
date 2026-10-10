import base64
from datetime import timedelta
from io import BytesIO
from pathlib import Path
import pytest
from PIL import Image
from sqlalchemy import select
from app.config import settings
from app.db import SessionLocal
from app.models import User,GoogleChallenge,CoverImage,PasswordReset,StorageDeletion,now
from app.security import digest,passwords
from .test_workflows import req,setup_club

HEADERS={'Origin':'http://testserver','X-Campus-Request':'1'}

def cover_body():
    b=BytesIO();Image.new('RGB',(60,60),'red').save(b,format='PNG')
    return {'image':base64.b64encode(b.getvalue()).decode()}

@pytest.fixture()
def google_signer(monkeypatch):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    from google.auth import jwt,crypt
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Test only')])
    cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(1).not_valid_before(now()-timedelta(days=1)).not_valid_after(now()+timedelta(days=1)).sign(key,hashes.SHA256())
    signer=crypt.RSASigner.from_string(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()),key_id='test')
    monkeypatch.setattr('google.oauth2.id_token._fetch_certs',lambda *a,**kw:{'test':cert.public_bytes(serialization.Encoding.PEM).decode()})
    monkeypatch.setattr(settings,'google_client_id','test.apps.googleusercontent.com')
    def token(nonce,**extra):
        claims={'iss':'https://accounts.google.com','aud':settings.google_client_id,'sub':'google-user-1','email':'googleuser@gmail.com','email_verified':True,'iat':int(now().timestamp()),'exp':int((now()+timedelta(minutes=10)).timestamp()),'nonce':nonce,'name':'Google Student',**extra}
        return jwt.encode(signer,claims).decode()
    return token

def challenge(client):
    r=client.post('/v1/auth/google/challenge',headers=HEADERS)
    assert r.status_code==200,r.text
    return r.json()['nonce']

def test_google_signup_returning_login_and_nonce_replay(client,google_signer):
    nonce=challenge(client);token=google_signer(nonce)
    assert client.post('/v1/auth/google',json={'credential':token}).status_code==403
    r=client.post('/v1/auth/google',headers=HEADERS,json={'credential':token})
    assert r.json()['status']=='profile_required'
    data={'credential':token,'name':'Google Student','usn':'1TE25CS123'}
    assert client.post('/v1/auth/google',headers=HEADERS,json={**data,'admin':True}).status_code==422
    r=client.post('/v1/auth/google',headers=HEADERS,json=data)
    assert r.json()['status']=='signed_in' and 'HttpOnly' in r.headers['set-cookie']
    me=client.get('/v1/me').json();assert me['admin'] is False and me['approved'] is True and 'google_sub' not in me
    client.cookies.set('bc_google_nonce',nonce,path='/v1/auth/google')
    assert client.post('/v1/auth/google',headers=HEADERS,json=data).status_code==401
    client.cookies.clear()
    nonce=challenge(client)
    assert client.post('/v1/auth/google',headers=HEADERS,json={'credential':google_signer(nonce)}).json()['status']=='signed_in'
    with SessionLocal() as db:assert len(list(db.scalars(select(User))))==1

@pytest.mark.parametrize('claims',[{'aud':'another-app'},{'iss':'evil.example'},{'exp':1},{'email_verified':False},{'nonce':'wrong'},{'email':'thirdparty@example.com'}])
def test_google_claims_rejected(client,google_signer,claims):
    nonce=challenge(client)
    extra=dict(claims);actual_nonce=extra.pop('nonce',nonce)
    r=client.post('/v1/auth/google',headers=HEADERS,json={'credential':google_signer(actual_nonce,**extra)})
    assert r.status_code in (401,403),r.text

def test_google_signature_and_college_domain(client,google_signer,monkeypatch):
    nonce=challenge(client);token=google_signer(nonce)
    segments=token.split('.');segments[2]=('A' if segments[2][0]!='A' else 'B')+segments[2][1:]
    assert client.post('/v1/auth/google',headers=HEADERS,json={'credential':'.'.join(segments)}).status_code==401
    monkeypatch.setattr(settings,'google_hosted_domain','college.example')
    assert client.post('/v1/auth/google',headers=HEADERS,json={'credential':token}).status_code==403
    monkeypatch.setattr(settings,'google_hosted_domain','')
    monkeypatch.setattr(settings,'allowed_email_domains',['college.example'])
    assert client.post('/v1/auth/google',headers=HEADERS,json={'credential':token}).status_code==403

def test_google_existing_account_requires_password_and_disabled_stays_disabled(client,actors,google_signer):
    nonce=challenge(client);token=google_signer(nonce,email='student@example.com',hd='example.com')
    r=client.post('/v1/auth/google',headers=HEADERS,json={'credential':token});assert r.json()['status']=='link_required'
    assert client.post('/v1/auth/google',headers=HEADERS,json={'credential':token,'existing_password':'wrong'}).status_code==401
    assert client.post('/v1/auth/google',headers=HEADERS,json={'credential':token,'existing_password':'secure-test-pass-123'}).json()['status']=='signed_in'
    assert client.get('/v1/me').json()['id']==actors['student']['id']
    client.cookies.clear()
    with SessionLocal() as db:db.get(User,actors['student']['id']).active=False;db.commit()
    nonce=challenge(client)
    assert client.post('/v1/auth/google',headers=HEADERS,json={'credential':google_signer(nonce,email='student@example.com',hd='example.com')}).status_code==403

def test_password_reset_single_use_expiry_and_session_revocation(client,actors,monkeypatch):
    sent=[];monkeypatch.setattr(settings,'smtp_host','test-mail');monkeypatch.setattr(settings,'smtp_from','sender@example.com')
    monkeypatch.setattr('app.auth_routes.send_password_reset',lambda email,url:sent.append((email,url)))
    def forgot(email):return client.post('/v1/auth/forgot-password',headers=HEADERS,json={'email':email})
    assert forgot('missing@example.com').json()==forgot('student@example.com').json()
    assert len(sent)==1
    forgot('student@example.com');assert len(sent)==1
    token=sent[0][1].split('#reset=')[1]
    with SessionLocal() as db:assert db.scalar(select(PasswordReset)).token_hash!=token
    assert client.post('/v1/auth/reset-password',json={'token':token,'password':'new-password-123'}).status_code==403
    assert client.post('/v1/auth/reset-password',headers=HEADERS,json={'token':token,'password':'new-password-123'}).status_code==200
    assert client.get('/v1/me',headers=actors['student']['headers']).status_code==401
    assert client.post('/v1/auth/reset-password',headers=HEADERS,json={'token':token,'password':'new-password-456'}).status_code==422
    assert client.post('/v1/auth/login',json={'email':'student@example.com','password':'new-password-123'}).status_code==200
    with SessionLocal() as db:
        db.add(PasswordReset(user_id=actors['student']['id'],token_hash=digest('x'*40),expires_at=now()-timedelta(seconds=1)));db.commit()
    assert client.post('/v1/auth/reset-password',headers=HEADERS,json={'token':'x'*40,'password':'new-password-456'}).status_code==422

def test_password_whitespace_preserved():
    from app.schemas import Signup,Login,ResetPasswordInput
    value='  a-long-password  '
    assert Login(email='a@example.com',password=value).password==value
    assert Signup(name='User',usn='ABC',email='a@example.com',password=value,otp='123456').password==value
    assert ResetPasswordInput(token='a'*40,password=value).password==value

def test_external_storage_replacement_cleanup_and_failure(client,actors,monkeypatch):
    from app import storage
    first=req(client,actors,'student','PUT','/me/cover',cover_body());id=first['cover_url'].split('/')[-1]
    with SessionLocal() as db:
        image=db.get(CoverImage,id);assert image.content is None and image.storage_backend=='local'
        old_key=image.storage_key;assert storage.local_path(old_key).exists()
    second=req(client,actors,'student','PUT','/me/cover',cover_body())
    assert not storage.local_path(old_key).exists()
    def fail(*a):raise storage.StorageError('secret storage credential')
    monkeypatch.setattr(storage,'put_image',fail)
    response=client.put('/v1/me/cover',headers=actors['student']['headers'],json=cover_body())
    assert response.status_code==503 and 'secret storage credential' not in response.text
    assert req(client,actors,'student','GET','/me')['cover_url']==second['cover_url']

def test_cleanup_retry_and_legacy_cover(client,actors,monkeypatch):
    from app import storage
    req(client,actors,'student','PUT','/me/cover',cover_body())
    original=storage.delete_image
    monkeypatch.setattr(storage,'delete_image',lambda *args:(_ for _ in ()).throw(storage.StorageError()))
    req(client,actors,'student','PUT','/me/cover',cover_body())
    with SessionLocal() as db:assert len(list(db.scalars(select(StorageDeletion))))==1
    monkeypatch.setattr(storage,'delete_image',original)
    with SessionLocal() as db:
        assert storage.drain_deletions(db)==0
        assert not list(db.scalars(select(StorageDeletion)))
        legacy=CoverImage(content=b'old-image');db.add(legacy);db.commit();id=legacy.id
    assert client.get('/v1/covers/'+id,headers=actors['student']['headers']).content==b'old-image'

def test_private_s3_adapter_uses_prefix_and_no_public_acl(client,monkeypatch):
    import boto3
    from botocore.stub import Stubber,ANY
    from app import storage
    client_s3=boto3.client('s3',region_name='us-east-1',aws_access_key_id='testing',aws_secret_access_key='testing')
    monkeypatch.setattr(storage,'s3_client',lambda:client_s3);monkeypatch.setattr(settings,'s3_bucket','test-bucket')
    key='12345678-1234-1234-1234-123456789012.jpg'
    with Stubber(client_s3) as stub:
        stub.add_response('put_object',{}, {'Bucket':'test-bucket','Key':'covers/'+key,'Body':b'image','ContentType':'image/jpeg','CacheControl':'private, max-age=300'})
        stub.add_response('get_object',{'Body':BytesIO(b'image')},{'Bucket':'test-bucket','Key':'covers/'+key})
        stub.add_response('delete_object',{}, {'Bucket':'test-bucket','Key':'covers/'+key})
        storage.put_image('s3',key,b'image');assert storage.read_image('s3',key)==b'image';storage.delete_image('s3',key)
        stub.assert_no_pending_responses()
    with pytest.raises(storage.StorageError):storage.read_image('local','../../etc/passwd')

def test_hidden_announcements_and_request_limit(client,actors):
    club=setup_club(client,actors)
    req(client,actors,'coordinator','POST',f'/clubs/{club}/announcements',{'title':'Private club update','body':'Hidden after club moderation'},201)
    req(client,actors,'admin','PATCH',f'/clubs/{club}/visibility',{'visible':False})
    assert req(client,actors,'student','GET','/announcements')==[]
    req(client,actors,'student','PUT',f'/clubs/{club}/follow',code=404)
    assert client.post('/v1/auth/login',content=b'x'*3_000_001).status_code==413

def test_cover_commit_failure_cleans_new_object(client,actors,monkeypatch):
    import app.main as main
    def fail(*args):raise RuntimeError('Simulated DB failure')
    monkeypatch.setattr(main,'save',fail)
    with pytest.raises(RuntimeError):req(client,actors,'student','PUT','/me/cover',cover_body())
    assert not list(Path(settings.media_root).glob('*.jpg'))
    with SessionLocal() as db:assert not list(db.scalars(select(CoverImage)))

def test_cors_allows_browser_auth_headers(client):
    response=client.options('/v1/auth/web-login',headers={'Origin':'http://localhost:5173','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type,x-campus-request'})
    assert response.status_code==200
    assert response.headers['access-control-allow-credentials']=='true'

def test_campus_nat_logins_use_separate_account_limits(client):
    from app.main import app,auth_limit,_attempts
    app.dependency_overrides.pop(auth_limit);_attempts.clear()
    for i in range(12):
        assert client.post('/v1/auth/login',json={'email':f'student{i}@example.com','password':'bad'}).status_code==401
    for _ in range(9):assert client.post('/v1/auth/login',json={'email':'student0@example.com','password':'bad'}).status_code==401
    assert client.post('/v1/auth/login',json={'email':'student0@example.com','password':'bad'}).status_code==429
    _attempts.clear()
