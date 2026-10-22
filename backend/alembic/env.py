from alembic import context
from app.db import engine,Base
from app import models
config=context.config
with engine.connect() as conn:
    context.configure(connection=conn,target_metadata=Base.metadata,compare_type=True)
    with context.begin_transaction(): context.run_migrations()
