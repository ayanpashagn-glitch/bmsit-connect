"""Local-only UI QA. Uses test-provider fixtures, never real Google/SMTP credentials."""
import json,os
from pathlib import Path
from . import browser_server
from app.config import settings
from app.main import app
import app.auth_routes as auth_routes
import uvicorn
settings.google_client_id='test.apps.googleusercontent.com'
settings.smtp_host='qa-mail';settings.smtp_from='qa@example.com'
# The browser provides only the fixture nonce here. Cryptographic verification is
# separately tested with signed tokens and local certificates in test_auth_storage.py.
def fixture_verify(credential):
    claims=json.loads(credential)
    return {'sub':'qa-google-user','email':'qa-google-user@gmail.com','email_verified':True,'name':'Google QA Student',**claims}
auth_routes.verify_google=fixture_verify
auth_routes.send_password_reset=lambda email,url:Path(os.environ['QA_RESET_FILE']).write_text(json.dumps({'email':email,'url':url}))
uvicorn.run(app,host='127.0.0.1',port=8000)
