"""Server-operator commands. Never expose these as public endpoints."""
import argparse
from getpass import getpass
from sqlalchemy import select
from .db import SessionLocal
from .models import User, LoginSession
from .security import passwords

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['create-admin','reset-password'])
    parser.add_argument('--email',required=True)
    parser.add_argument('--name',default='College Administrator')
    parser.add_argument('--usn',default='STAFF-ADMIN')
    args=parser.parse_args()
    password=getpass('New password (12–128 characters): ')
    if not 12<=len(password)<=128: parser.error('Password must contain 12–128 characters')
    if password!=getpass('Confirm password: '): parser.error('Passwords do not match')
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email==args.email.lower()))
        if args.command=='create-admin':
            if user: parser.error('Account already exists; no automatic privilege promotion')
            user=User(email=args.email.lower(),usn=args.usn.upper(),name=args.name,approved=True,active=True,admin=True)
            db.add(user)
        else:
            if not user: parser.error('Account not found')
            for session in db.scalars(select(LoginSession).where(LoginSession.user_id==user.id)):
                db.delete(session)
        user.password_hash=passwords.hash(password)
        db.commit()
    print('Account updated successfully.')

if __name__=='__main__': main()
