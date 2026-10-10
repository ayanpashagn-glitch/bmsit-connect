"""Run after migrations: python -m examples.check_database"""
from sqlalchemy import inspect, text
from app.db import engine
from app.models import Base
with engine.connect() as connection:
    connection.execute(text('SELECT 1'))
    present=set(inspect(connection).get_table_names())
    missing=set(Base.metadata.tables)-present
    if missing:
        raise SystemExit('Connection works; missing tables: '+', '.join(sorted(missing))+'. Run alembic upgrade head.')
    print('Database connection and all backend tables verified.')
