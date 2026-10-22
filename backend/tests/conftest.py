import os,tempfile
from pathlib import Path
root=Path(tempfile.mkdtemp(prefix='approvallens-tests-'))
os.environ['DATABASE_URL']='sqlite:///'+str(root/'test.db')
os.environ['STORAGE_DIR']=str(root/'private')
os.environ['DEMO_ENABLED']='true'
import pytest
from fastapi.testclient import TestClient
from app.db import Base,engine,SessionLocal
from app.models import *
from app.main import app
from app.security import hasher
from app.seed import seed

class Limiter:
    counts={}
    def incr(self,key): self.counts[key]=self.counts.get(key,0)+1;return self.counts[key]
    def expire(self,*a): pass
@pytest.fixture(scope='session',autouse=True)
def database():
    Base.metadata.create_all(engine);seed()
@pytest.fixture
def client(monkeypatch):
    import app.main as main
    Limiter.counts={}
    monkeypatch.setattr(main.Redis,'from_url',lambda *a,**k:Limiter())
    monkeypatch.setattr(main.process_run,'delay',lambda *a,**k:None)
    return TestClient(app)
def sign_in(client,role='applicant'):
    r=client.post('/api/v1/auth/login',json={'email':role+'@demo.local','password':'DemoOnly!2026'})
    assert r.status_code==200,r.text
    client.headers['X-CSRF-Token']=r.json()['csrf']
    return r.json()['user']
