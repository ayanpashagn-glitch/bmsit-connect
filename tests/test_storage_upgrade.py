import os,subprocess,sys,sqlite3
from pathlib import Path

def test_existing_cover_migration_keeps_url_and_removes_blob(tmp_path):
    root=Path(__file__).resolve().parents[1]
    database=tmp_path/'upgrade.db';media=tmp_path/'covers'
    env={**os.environ,'DATABASE_URL':'sqlite:///'+str(database),'STORAGE_BACKEND':'local','MEDIA_ROOT':str(media)}
    def run(*args):subprocess.run([sys.executable,*args],cwd=root,env=env,check=True,capture_output=True)
    run('-m','alembic','upgrade','b81c7ad48d12')
    id='12345678-1234-1234-1234-123456789012'
    with sqlite3.connect(database) as db:db.execute('INSERT INTO bc_cover_images (id,created_at,content) VALUES (?,?,?)',(id,'2026-09-25',b'legacy-cover-bytes'))
    run('-m','alembic','upgrade','head')
    with sqlite3.connect(database) as db:assert db.execute('SELECT content,storage_backend FROM bc_cover_images').fetchone()==(b'legacy-cover-bytes','database')
    run('-m','app.storage_maintenance','migrate')
    run('-m','app.storage_maintenance','migrate')
    with sqlite3.connect(database) as db:assert db.execute('SELECT id,content,storage_key,storage_backend,size_bytes FROM bc_cover_images').fetchone()==(id,None,id+'.jpg','local',len(b'legacy-cover-bytes'))
    assert (media/(id+'.jpg')).read_bytes()==b'legacy-cover-bytes'
