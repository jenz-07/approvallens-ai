"""Persist evidence graph and claims per validation snapshot."""
from alembic import op
import sqlalchemy as sa
revision='9c3e12'
down_revision='8b2d91_job_outbox'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('evidence_analyses',sa.Column('id',sa.String(36),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('run_id',sa.String(36),sa.ForeignKey('validation_runs.id'),nullable=False),sa.Column('application_id',sa.String(36),sa.ForeignKey('applications.id'),nullable=False),sa.Column('pipeline_version',sa.String(100),nullable=False),sa.Column('result',sa.JSON(),nullable=False),sa.UniqueConstraint('run_id'))
    op.create_index('ix_evidence_analyses_run_id','evidence_analyses',['run_id'])
    op.create_index('ix_evidence_analyses_application_id','evidence_analyses',['application_id'])
    if op.get_bind().dialect.name=='postgresql':
        from app.db import Base
        from app import models
        for table in Base.metadata.tables:op.execute(sa.text('ALTER TABLE "'+table+'" ENABLE ROW LEVEL SECURITY'))

def downgrade():
    op.drop_table('evidence_analyses')
