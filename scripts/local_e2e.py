"""Run isolated local integration services and Playwright in one process namespace.
For contributor QA only. Docker Compose is the standard user setup.
Requires a Redis binary on PATH (or REDIS_SERVER override), Python venv, npm ci,
and npx playwright install chromium. Uses SQLite only for this portable test harness.
"""
import os,subprocess,tempfile,time,urllib.request,shutil,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
python=sys.executable
work=Path(tempfile.mkdtemp(prefix='approval-e2e-'))
env={**os.environ,'DATABASE_URL':'sqlite:///'+str(work/'app.db'),'STORAGE_DIR':str(work/'private'),'DEMO_ENABLED':'true','ENVIRONMENT':'development','REDIS_URL':'redis://127.0.0.1:16379/0','ALLOWED_ORIGIN':'http://127.0.0.1:13000','API_INTERNAL_URL':'http://127.0.0.1:18000','NEXT_TELEMETRY_DISABLED':'1','PLAYWRIGHT_BASE_URL':'http://127.0.0.1:13000'}
procs=[];logs=[]
def start(cmd,cwd,name):
 f=(work/(name+'.log')).open('w');logs.append(f);p=subprocess.Popen(cmd,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT);procs.append(p)
def run(cmd,cwd):subprocess.run(cmd,cwd=cwd,env=env,check=True)
def wait(url):
 deadline=time.time()+45
 while time.time()<deadline:
  try:
   with urllib.request.urlopen(url,timeout=2) as r:
    if r.status==200:return
  except Exception:time.sleep(.3)
 raise RuntimeError('Service failed to start: '+url)
try:
 run([python,'-m','alembic','upgrade','head'],root/'backend')
 run([python,'-m','app.seed'],root/'backend')
 start([os.environ.get('REDIS_SERVER','redis-server'),'--port','16379','--bind','127.0.0.1','--save','','--appendonly','no'],root,'redis')
 start([python,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port','18000'],root/'backend','api')
 start([python,'-m','celery','-A','app.worker.celery','worker','--pool=solo','--concurrency=1','--loglevel=WARNING'],root/'backend','worker')
 start([python,'-m','app.dispatcher'],root/'backend','dispatcher')
 start(['node','node_modules/next/dist/bin/next','start','--hostname','127.0.0.1','--port','13000'],root/'frontend','frontend')
 wait('http://127.0.0.1:18000/api/v1/health');wait('http://127.0.0.1:13000')
 run(['npm','run','test:e2e'],root/'frontend')
finally:
 for p in procs:p.terminate()
 for p in procs:
  try:p.wait(timeout=5)
  except subprocess.TimeoutExpired:p.kill()
 for f in logs:f.close()
 print('Service logs:',work)
