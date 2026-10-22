"""Transactional outbox dispatcher. At-least-once delivery; worker claims are idempotent.
Run one service with `python -m app.dispatcher`. Multiple PostgreSQL dispatchers
are safe through row locks; single instance only for SQLite development.
"""
import signal,threading
from datetime import timedelta,timezone
from sqlalchemy import select
from .db import SessionLocal
from .models import JobDispatch,ValidationRun,Application,AuditEvent,now
from .worker import process_run

def tick():
    with SessionLocal() as db:
        # Hard task timeout is 10m; recovery lease is deliberately longer (15m).
        stale=db.scalars(select(ValidationRun).where(ValidationRun.status.in_(['Extracting','Validating']),ValidationRun.heartbeat<now()-timedelta(minutes=15)).with_for_update(skip_locked=True)).all()
        for run in stale:
            run.status='Queued' if run.attempts<6 else 'Failed'
            run.stage='Recovering interrupted worker' if run.attempts<6 else 'Retry limit reached'
            run.error='Previous worker did not finish within its lease';run.heartbeat=now()
            job=db.scalar(select(JobDispatch).where(JobDispatch.run_id==run.id))
            if job:job.published_at=None
            else:db.add(JobDispatch(run_id=run.id))
            db.add(AuditEvent(application_id=run.application_id,event='worker_lease_recovered',details={'run_id':run.id}))
        db.commit()
    with SessionLocal() as db:
        jobs=db.scalars(select(JobDispatch).join(ValidationRun).where(ValidationRun.status=='Queued').order_by(JobDispatch.created_at).limit(100).with_for_update(of=JobDispatch,skip_locked=True)).all()
        for job in jobs:
            if job.published_at and job.published_at.replace(tzinfo=timezone.utc)>now()-timedelta(seconds=60):continue
            try:
                process_run.delay(job.run_id)
                job.published_at=now();job.last_error=None
            except Exception as exc:
                job.last_error=type(exc).__name__+': broker dispatch failed; will retry'
            job.attempts+=1
        db.commit()

if __name__=='__main__':
    stop=threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.set())
    while not stop.is_set():
        try:tick()
        except Exception as exc:print('Dispatcher retry:',type(exc).__name__,flush=True)
        stop.wait(10)
