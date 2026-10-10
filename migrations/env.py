from alembic import context
from app.db import Base, engine
from app import models
config=context.config

def include_name(name, type_, parent_names):
    # Keep autogeneration away from tables owned by another application.
    return type_ != 'table' or name.startswith('bc_')

if context.is_offline_mode():
    context.configure(url=engine.url, target_metadata=Base.metadata,include_name=include_name, literal_binds=True, dialect_opts={'paramstyle':'named'}, version_table='bc_alembic_version')
    with context.begin_transaction(): context.run_migrations()
else:
    with engine.connect() as connection:
        context.configure(connection=connection,target_metadata=Base.metadata,include_name=include_name,version_table='bc_alembic_version')
        with context.begin_transaction(): context.run_migrations()
