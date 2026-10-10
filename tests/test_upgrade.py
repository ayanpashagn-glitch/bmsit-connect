"""Verify a v0.2 database upgrade retains existing access settings and records."""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

def test_upgrade_retains_accounts_and_clubs(tmp_path):
    path=tmp_path/'upgrade.db'
    env={**os.environ,'DATABASE_URL':'sqlite:///'+str(path)}
    root=Path(__file__).resolve().parents[1]
    def migrate(target):
        subprocess.run([sys.executable,'-m','alembic','upgrade',target],cwd=root,env=env,check=True,capture_output=True)
    migrate('dcd6babc803a')
    with sqlite3.connect(path) as db:
        for name,approved,active in [('active',1,1),('disabled',1,0),('legacy-pending',0,1)]:
            db.execute('INSERT INTO bc_users (id,created_at,email,usn,name,password_hash,approved,active,admin,branch,year,skills,bio) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',(name,'2026-09-25',name+'@example.com',name,name,'test-hash',approved,active,0,'CSE',1,'Python','Bio'))
        db.execute('INSERT INTO bc_clubs (id,created_at,name,description,category,active) VALUES (?,?,?,?,?,?)',('club','2026-09-25','ASTRA','Existing club','Technology',1))
    migrate('head')
    migrate('head')
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT id,approved,active FROM bc_users ORDER BY id').fetchall()==[('active',1,1),('disabled',1,0),('legacy-pending',0,1)]
        assert db.execute('SELECT name,cover_url FROM bc_clubs').fetchall()==[('ASTRA',None)]
        for table in ['bc_email_otps','bc_cover_images','bc_coordinator_requests']:
            assert db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]==0
