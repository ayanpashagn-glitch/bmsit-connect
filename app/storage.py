"""Private cover storage. Local mode requires a persistent volume in deployment."""
from pathlib import Path
import re
from functools import lru_cache
from sqlalchemy import select
from .config import settings
from .models import StorageDeletion

class StorageError(Exception): pass

def valid_key(key):
    if not key or not re.fullmatch(r'[0-9a-f-]{36}\.jpg',key): raise StorageError('Invalid storage key')
    return key

def local_path(key):
    root=Path(settings.media_root).resolve()
    return root/valid_key(key)

@lru_cache(maxsize=1)
def s3_client():
    import boto3
    from botocore.config import Config
    if not settings.s3_bucket: raise StorageError('Set S3_BUCKET')
    kwargs={'region_name':settings.s3_region,'config':Config(connect_timeout=5,read_timeout=10,retries={'max_attempts':2},signature_version='s3v4')}
    if settings.s3_endpoint_url: kwargs['endpoint_url']=settings.s3_endpoint_url
    if settings.s3_access_key_id:
        kwargs['aws_access_key_id']=settings.s3_access_key_id
        kwargs['aws_secret_access_key']=settings.s3_secret_access_key
    return boto3.client('s3',**kwargs)

def put_image(backend,key,content):
    valid_key(key)
    try:
        if backend=='local':
            p=local_path(key);p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('xb') as f: f.write(content)
        elif backend=='s3':
            s3_client().put_object(Bucket=settings.s3_bucket,Key='covers/'+key,Body=content,ContentType='image/jpeg',CacheControl='private, max-age=300')
        else: raise StorageError('Unknown storage backend')
    except Exception as e: raise StorageError('Image write failed') from e

def read_image(backend,key):
    valid_key(key)
    try:
        if backend=='local':return local_path(key).read_bytes()
        if backend=='s3':
            body=s3_client().get_object(Bucket=settings.s3_bucket,Key='covers/'+key)['Body']
            try: return body.read()
            finally: body.close()
        raise StorageError('Unknown storage backend')
    except Exception as e: raise StorageError('Image read failed') from e

def delete_image(backend,key):
    valid_key(key)
    try:
        if backend=='local':local_path(key).unlink(missing_ok=True)
        elif backend=='s3':s3_client().delete_object(Bucket=settings.s3_bucket,Key='covers/'+key)
        else:raise StorageError('Unknown storage backend')
    except Exception as e:raise StorageError('Image delete failed') from e

def drain_deletions(db,limit=100):
    failed=0
    for item in db.scalars(select(StorageDeletion).order_by(StorageDeletion.created_at,StorageDeletion.id).limit(limit).with_for_update(skip_locked=True)):
        try: delete_image(item.storage_backend,item.storage_key)
        except StorageError:failed+=1;continue
        db.delete(item)
    db.commit()
    return failed
