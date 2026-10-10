"""Disposable browser QA server. Never use this as a deployment entry point.
Usage: QA_OTP_FILE=/absolute/test-only/path DATABASE_URL=sqlite:////absolute/test-only.db python -m tests.browser_server
Only the local SMTP transport is replaced; registration still requires the generated OTP.
"""
import os
import json
from pathlib import Path
import uvicorn
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from app.config import settings
from app.db import SessionLocal
from app.models import User
from app.security import passwords
import app.main as main

if not settings.database_url.startswith('sqlite:') or 'qa' not in settings.database_url:
    raise SystemExit('Requires a disposable SQLite database path containing qa')
sink=Path(os.environ['QA_OTP_FILE'])
if not sink.is_absolute(): raise SystemExit('QA_OTP_FILE must be absolute')
command.upgrade(Config('alembic.ini'),'head')
with SessionLocal() as db:
    for role in ('admin','coordinator','teammate'):
        email=role+'@example.com'
        if not db.scalar(select(User).where(User.email==email)):
            db.add(User(email=email,usn='QA-'+role,name='QA '+role.title(),password_hash=passwords.hash(os.environ['QA_PASSWORD']),approved=True,admin=role=='admin'))
    db.commit()
def capture(email,code):
    sink.write_text(json.dumps({'email':email,'code':code}))
    sink.chmod(0o600)
main.send_otp=capture
if __name__=='__main__':uvicorn.run(main.app,host='127.0.0.1',port=8000)
