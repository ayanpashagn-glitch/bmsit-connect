"""One-app launcher: migrations, first admin setup, UI and API."""
import os
import sys
from pathlib import Path

def main():
    root=Path(__file__).resolve().parent
    os.chdir(root)
    if not os.environ.get('DATABASE_URL') and not (root/'.env').exists():
        raise SystemExit('Copy .env.example to .env and set DATABASE_URL, then run again.')
    from app.config import settings
    from app.db import SessionLocal
    from app.models import User
    from sqlalchemy import select
    from alembic.config import Config
    from alembic import command
    try:
        command.upgrade(Config(str(root/'alembic.ini')),'head')
    except Exception:
        raise SystemExit('Database setup failed. Check DATABASE_URL, database access and migration permissions. Your connection string has not been printed.')
    with SessionLocal() as db:
        has_admin=db.scalar(select(User.id).where(User.admin==True,User.active==True))
    if not has_admin:
        if not sys.stdin.isatty():
            raise SystemExit('Create your first administrator with: python -m app.cli create-admin --email YOUR_EMAIL . Then start again.')
        print('\nFirst start: create your college administrator account.')
        from pydantic import TypeAdapter, EmailStr
        email=input('Admin email: ').strip()
        try: TypeAdapter(EmailStr).validate_python(email)
        except ValueError: raise SystemExit('Enter a valid administrator email address.')
        name=input('Admin name: ').strip() or 'College Administrator'
        from app.cli import main as create_admin
        sys.argv=['cli','create-admin','--email',email,'--name',name]
        create_admin()
    if not (root/'web/index.html').is_file():
        raise SystemExit('Frontend build missing. Run pnpm build inside frontend, then retry.')
    import uvicorn
    port=int(os.environ.get('PORT','8000'))
    host=os.environ.get('HOST','127.0.0.1')
    print(f'\nBMSIT Connect is starting at http://localhost:{port}')
    uvicorn.run('app.main:app',host=host,port=port,proxy_headers=False)

if __name__=='__main__':main()
