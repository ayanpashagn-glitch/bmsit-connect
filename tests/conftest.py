import os
import tempfile
from pathlib import Path
# Never run tests against the user's configured database. Opt-in separate disposable PG database only.
os.environ['DATABASE_URL']=os.environ.get('TEST_DATABASE_URL','sqlite:///' + str(Path(tempfile.gettempdir()) / 'bmsit-isolated-test.db'))
import pytest
from fastapi.testclient import TestClient
from app.main import app, auth_limit
from app.db import Base, engine, SessionLocal
from app.models import User
from app.security import passwords, issue_token

@pytest.fixture()
def client(tmp_path,monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings,"storage_backend","local")
    monkeypatch.setattr(settings,"media_root",str(tmp_path/"covers"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    app.dependency_overrides[auth_limit]=lambda: None
    with TestClient(app) as c: yield c
    app.dependency_overrides.clear()

@pytest.fixture()
def actors(client):
    out={}
    with SessionLocal() as db:
        for role in ['admin','coordinator','student','other','outsider']:
            user=User(email=f'{role}@example.com',usn=role,name=role,
                      password_hash=passwords.hash('secure-test-pass-123'),approved=True,admin=role=='admin')
            db.add(user); db.flush()
            token=issue_token(db,user)
            out[role]={'id':user.id,'headers':{'Authorization':'Bearer '+token}}
        db.commit()
    return out
