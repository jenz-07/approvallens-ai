"""Small-demo database queue runner, hosted within one API instance.
A child process bounds task runtime and isolates extraction from API threads.
Redis is still used for login limits, but not for embedded job dispatch.
"""
import asyncio
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import timedelta
from sqlalchemy import select, text
from .config import settings
from .db import engine, SessionLocal
from .models import ValidationRun, AuditEvent, now

log=logging.getLogger(__name__)
LOCK_ID=73124019

def execute(run_id, stop, timeout=600):
    child=subprocess.Popen([sys.executable,'-m','app.embedded_job',run_id],start_new_session=True)
    deadline=time.monotonic()+timeout
    try:
        while child.poll() is None:
            if stop.wait(0.25) or time.monotonic()>=deadline:
                return False
        return child.returncode==0
    finally:
        if child.poll() is None:
            # Kill the task and any OCR descendants before allowing a retry.
            os.killpg(child.pid,signal.SIGKILL)
            child.wait()

def tick(stop):
    # PostgreSQL session lock prevents overlapping deployments from running
    # two tasks. Session pooler/direct connections only, never transaction mode.
    with engine.connect() as lock:
        postgres=engine.dialect.name=='postgresql'
        if postgres:
            acquired=lock.scalar(text('SELECT pg_try_advisory_lock(:key)'),{'key':LOCK_ID})
            lock.commit()
            if not acquired:return False
        try:
            with SessionLocal() as db:
                stale=db.scalars(select(ValidationRun).where(
                    ValidationRun.status.in_(['Extracting','Validating']),
                    ValidationRun.heartbeat<now()-timedelta(minutes=15))).all()
                for run in stale:
                    run.status='Queued' if run.attempts<3 else 'Failed'
                    run.stage='Recovering interrupted demo task'
                    run.heartbeat=now()
                    db.add(AuditEvent(application_id=run.application_id,event='worker_lease_recovered',details={'run_id':run.id}))
                db.commit()
                run=db.scalar(select(ValidationRun).where(ValidationRun.status=='Queued').order_by(ValidationRun.created_at))
                if not run or stop.is_set():return False
                run_id=run.id
            succeeded=execute(run_id,stop)
            if not succeeded:
                with SessionLocal() as db:
                    run=db.get(ValidationRun,run_id)
                    if run and run.status!='Completed':
                        # Even a failure before the child claims work must consume a retry.
                        if run.status=='Queued':run.attempts+=1
                        run.status='Queued' if run.attempts<3 else 'Failed'
                        run.stage='Retrying interrupted demo task' if run.attempts<3 else 'Demo task retry limit reached'
                        run.error='Processing interrupted or exceeded the demo runtime limit'
                        run.heartbeat=now();db.commit()
            return True
        finally:
            if postgres:
                lock.execute(text('SELECT pg_advisory_unlock(:key)'),{'key':LOCK_ID})
                lock.commit()

def loop(stop):
    while not stop.is_set():
        try:tick(stop)
        except Exception:
            # Do not log connection strings or document content.
            log.warning('Embedded queue unavailable; retrying')
        stop.wait(3)

@asynccontextmanager
async def lifespan(app):
    if settings.processing_mode!='embedded':
        yield
        return
    stop=threading.Event()
    thread=threading.Thread(target=loop,args=(stop,),daemon=True,name='demo-queue')
    thread.start()
    try:yield
    finally:
        stop.set()
        await asyncio.to_thread(thread.join,5)
