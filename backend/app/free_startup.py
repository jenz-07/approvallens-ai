"""Migrate and optionally bootstrap without requiring a paid Render shell."""
import os
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from .db import engine
from .bootstrap import bootstrap

def main():
    with engine.connect() as lock:
        postgres=engine.dialect.name=='postgresql'
        if postgres:
            lock.execute(text('SELECT pg_advisory_lock(73124020)'));lock.commit()
        try:
            command.upgrade(Config('alembic.ini'),'head')
            email=os.environ.get('BOOTSTRAP_ADMIN_EMAIL')
            password=os.environ.get('BOOTSTRAP_ADMIN_PASSWORD')
            if bool(email)!=bool(password):raise SystemExit('Set both bootstrap credentials or neither')
            if email:bootstrap(email,password,skip_existing=True)
        finally:
            if postgres:
                lock.execute(text('SELECT pg_advisory_unlock(73124020)'));lock.commit()
if __name__=='__main__':main()
