"""Run while uploads are paused: python -m app.storage_maintenance migrate | cleanup.
Migrate existing DB/local covers into the configured backend, retaining URLs.
"""
import argparse
from sqlalchemy import select,delete
from .config import settings
from .db import SessionLocal
from .models import CoverImage, StorageDeletion, GoogleChallenge, PasswordReset, EmailOTP, LoginSession, now
from .storage import put_image, read_image, delete_image, drain_deletions, StorageError

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['migrate','cleanup']);args=p.parse_args()
    with SessionLocal() as db:
        if args.action=='migrate':
            ids=list(db.scalars(select(CoverImage.id).where(CoverImage.storage_backend!=settings.storage_backend)))
            for id in ids:
                item=db.scalar(select(CoverImage).where(CoverImage.id==id).with_for_update())
                if item.storage_backend==settings.storage_backend:continue
                content=item.content if item.storage_backend=='database' else read_image(item.storage_backend,item.storage_key)
                key=item.id+'.jpg'
                put_image(settings.storage_backend,key,content)
                old_backend,old_key=item.storage_backend,item.storage_key
                if old_key:db.add(StorageDeletion(storage_backend=old_backend,storage_key=old_key))
                item.content=None;item.storage_key=key;item.storage_backend=settings.storage_backend;item.size_bytes=len(content)
                try:db.commit()
                except Exception:
                    db.rollback()
                    try:delete_image(settings.storage_backend,key)
                    except StorageError:
                        db.add(StorageDeletion(storage_backend=settings.storage_backend,storage_key=key));db.commit()
                    raise
            print(f'Migrated {len(ids)} covers; existing cover URLs retained.')
        failed=drain_deletions(db)
        for model,column in [(GoogleChallenge,GoogleChallenge.expires_at),(PasswordReset,PasswordReset.expires_at),(EmailOTP,EmailOTP.expires_at),(LoginSession,LoginSession.expires_at)]:
            db.execute(delete(model).where(column<now()))
        db.commit()
        print(f'Cleanup complete; {failed} object deletions pending retry.')
        if failed:raise SystemExit(1)
if __name__=='__main__':main()
