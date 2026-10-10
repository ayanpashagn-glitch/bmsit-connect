from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

class Base(DeclarativeBase):
    pass

pool_options = {} if settings.database_url.startswith('sqlite:') else {
    'pool_size': settings.db_pool_size, 'max_overflow': settings.db_max_overflow,
    'pool_timeout': 10, 'pool_recycle': 1800,
}
engine = create_engine(settings.database_url, pool_pre_ping=True, **pool_options)
if engine.dialect.name == 'sqlite':
    @event.listens_for(engine, 'connect')
    def foreign_keys(conn, _):
        conn.execute('PRAGMA foreign_keys=ON')
SessionLocal = sessionmaker(engine, expire_on_commit=False)

def get_db():
    with SessionLocal() as db:
        yield db
