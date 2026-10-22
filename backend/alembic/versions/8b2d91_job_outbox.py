"""Durable validation dispatch outbox, including pending legacy jobs."""
from alembic import op
import sqlalchemy as sa
revision='8b2d91_job_outbox'
down_revision='60a4d94e190d'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('job_dispatches',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('run_id',sa.String(36),sa.ForeignKey('validation_runs.id'),nullable=False),
        sa.Column('published_at',sa.DateTime(timezone=True)),
        sa.Column('attempts',sa.Integer(),nullable=False),
        sa.Column('last_error',sa.Text()))
    op.create_index('ix_job_dispatches_run_id','job_dispatches',['run_id'],unique=True)
    op.execute("INSERT INTO job_dispatches (id,created_at,run_id,attempts) SELECT id,CURRENT_TIMESTAMP,id,0 FROM validation_runs WHERE status IN ('Queued','Extracting','Validating')")

def downgrade():
    op.drop_table('job_dispatches')
