import os, subprocess, sys, threading
from datetime import timedelta
from sqlalchemy import select
from app.config import settings
from app.db import SessionLocal
from app.models import Application,User,ValidationRun,EvidenceAnalysis,now
from app.main import enqueue,dispatch
from app import embedded
from .conftest import sign_in
from .test_workflow import payload,upload
from app.seed import synthetic_pdf

def new_run(client,key):
    sign_in(client)
    aid=client.post('/api/v1/applications',json=payload(client,key)).json()['id']
    uploaded=upload(client,aid,synthetic_pdf(['Institution Name: Synthetic Institute of Technology','Institution Identifier: SYN-001','Intake: 60']))
    assert uploaded.status_code in (200,201),uploaded.text
    with SessionLocal() as db:
        # Isolate the embedded queue from unrelated pending fixture jobs.
        for old in db.scalars(select(ValidationRun).where(ValidationRun.status=='Queued')):old.status='Failed'
        a=db.get(Application,aid);u=db.scalar(select(User).where(User.email=='applicant@demo.local'))
        run,_=enqueue(db,u,a,key);db.commit();return run.id

def test_embedded_processes_durable_queue_without_celery(client,monkeypatch):
    import app.main as main
    rid=new_run(client,'free-persisted')
    monkeypatch.setattr(settings,'processing_mode','embedded')
    def forbidden(*a,**kw):raise AssertionError('No Celery dispatch in embedded mode')
    monkeypatch.setattr(main.process_run,'delay',forbidden)
    with SessionLocal() as db:dispatch(db,db.get(ValidationRun,rid))
    assert embedded.tick(threading.Event())
    with SessionLocal() as db:
        assert db.get(ValidationRun,rid).status=='Completed'
        assert db.scalar(select(EvidenceAnalysis).where(EvidenceAnalysis.run_id==rid))

def test_embedded_recovers_stale_and_bounds_failure_retries(client,monkeypatch):
    rid=new_run(client,'free-recovery')
    with SessionLocal() as db:
        r=db.get(ValidationRun,rid);r.status='Extracting';r.attempts=1;r.heartbeat=now()-timedelta(minutes=16);db.commit()
    assert embedded.tick(threading.Event())
    with SessionLocal() as db:assert db.get(ValidationRun,rid).status=='Completed'
    rid=new_run(client,'free-failure')
    monkeypatch.setattr(embedded,'execute',lambda *a:False)
    for _ in range(3):assert embedded.tick(threading.Event())
    with SessionLocal() as db:
        r=db.get(ValidationRun,rid);assert r.status=='Failed' and r.attempts==3

def test_child_timeout_kills_process_group(monkeypatch):
    class Child:
        pid=1234
        killed=False
        def poll(self):return None
        def wait(self):self.killed=True
    child=Child();calls=[]
    monkeypatch.setattr(embedded.subprocess,'Popen',lambda *a,**kw:child)
    monkeypatch.setattr(embedded.os,'killpg',lambda *a:calls.append(a))
    assert not embedded.execute('fake',threading.Event(),timeout=0)
    assert child.killed and calls[0][0]==1234

def test_free_startup_migrates_bootstraps_and_preserves_admin(tmp_path):
    env={**os.environ,'DATABASE_URL':'sqlite:///'+str(tmp_path/'fresh.db'),'STORAGE_DIR':str(tmp_path/'private'),'BOOTSTRAP_ADMIN_EMAIL':'owner@example.test','BOOTSTRAP_ADMIN_PASSWORD':'UniqueLocalTest!123'}
    for _ in range(2):subprocess.run([sys.executable,'-m','app.free_startup'],env=env,check=True,capture_output=True)
    check="from app.db import SessionLocal; from app.models import User; from sqlalchemy import select; db=SessionLocal(); users=db.scalars(select(User)).all(); assert len(users)==1 and users[0].email=='owner@example.test'"
    subprocess.run([sys.executable,'-c',check],env=env,check=True,capture_output=True)
