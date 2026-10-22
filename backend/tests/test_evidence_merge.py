from sqlalchemy import select,func
from app.db import SessionLocal
from app.models import User,Assignment,ValidationRun,EvidenceAnalysis,Correction
from app.worker import run_pipeline
from app.seed import synthetic_pdf
from .test_workflow import payload,upload,workspace
from .conftest import sign_in

def setup_evidence(client):
    sign_in(client)
    aid=client.post('/api/v1/applications',json=payload(client,'Merged evidence test')).json()['id']
    versions=[]
    for intake in (60,120):
        data=synthetic_pdf(['Institution Name: Synthetic Institute of Technology','Institution Identifier: SYN-001','Address: Demo Campus',f'Intake: {intake}','Reference Number: SHARED-001','Issue Date: 2024-01-01','Expiry Date: 2027-01-01'])
        versions.append(upload(client,aid,data).json()['id'])
    with SessionLocal() as db:
        reviewer=db.scalar(select(User).where(User.role=='reviewer'));db.add(Assignment(application_id=aid,user_id=reviewer.id));db.commit()
    response=client.post(f'/api/v1/applications/{aid}/transition',json={'status':'Submitted','reason':'Test merged processing'});assert response.status_code==200,response.text
    run=workspace(client,aid)['runs'][0];run_pipeline(run['id']);return aid,run['id'],versions

def test_persisted_graph_review_and_access(client):
    aid,rid,versions=setup_evidence(client)
    base=f'/api/v1/applications/{aid}'
    assert client.get(base+'/evidence-graph').status_code==403
    sign_in(client,'reviewer');r=client.get(base+'/cross-document-findings?run_id='+rid);assert r.status_code==200,r.text
    data=r.json();f=next(f for f in data['findings'] if f['unit']=='institution.intake' and f['finding_type']=='contradiction')
    assert len(f['evidence_ids'])==2 and f['calibrated_probability'] is None
    assert set(data['input_version_ids'])==set(versions)
    assert any(c['field_name']=='institution_id' for c in data['claims'])
    action=client.post(base+'/cross-document-findings/review',json={'run_id':rid,'finding_id':f['finding_id'],'status':'Acknowledged','reason':'Checking both source pages'})
    assert action.status_code==200,action.text
    changed=client.get(base+'/cross-document-findings?run_id='+rid).json()
    assert next(x for x in changed['findings'] if x['finding_id']==f['finding_id'])['reviewed_status']=='Acknowledged'
    run_pipeline(rid)
    with SessionLocal() as db:assert db.scalar(select(func.count()).select_from(EvidenceAnalysis).where(EvidenceAnalysis.run_id==rid))==1
    fake=client.post(base+'/cross-document-findings/review',json={'run_id':rid,'finding_id':'fake','status':'Resolved','reason':'Invalid target'});assert fake.status_code==404
    assert client.get(base+'/report').content.startswith(b'%PDF')

def test_graph_corrections_are_snapshot_bound(client):
    aid,rid,vids=setup_evidence(client)
    from app.evidence_bridge import analyze_run
    with SessionLocal() as db:
        run=db.get(ValidationRun,rid);before=db.scalar(select(EvidenceAnalysis).where(EvidenceAnalysis.run_id==rid)).result
        reviewer=db.scalar(select(User).where(User.role=='reviewer'))
        db.add(Correction(version_id=vids[1],name='intake',value='90',reason='First correction',actor_id=reviewer.id));db.add(Correction(version_id=vids[1],name='intake',value='60',reason='Latest correction',actor_id=reviewer.id));db.commit()
        assert analyze_run(db,run)['findings']==before['findings']
        # Simulate a newly pinned input. Persisted original run is not mutated.
        from types import SimpleNamespace
        snap=dict(run.input_snapshot,corrections=[{'version_id':vids[1],'name':'intake','value':'90','reason':'First'},{'version_id':vids[1],'name':'intake','value':'60','reason':'Latest'}])
        new=analyze_run(db,SimpleNamespace(id='new',application_id=aid,input_snapshot=snap))
        values=[c['raw_value'] for c in new['claims'] if c['document_id']==vids[1] and c['field_name']=='intake']
        assert values==['60']
        assert not any(f['unit']=='institution.intake' and f['finding_type']=='contradiction' for f in new['findings'])

def test_backend_engine_has_no_optional_research_dependency():
    import subprocess,sys
    code="""import sys
class Deny:
 def find_spec(self,name,*args):
  if name.split('.')[0] in ('numpy','sklearn','scipy','matplotlib','networkx','cv2'): raise ImportError('Optional dependency '+name)
sys.meta_path.insert(0,Deny())
from ml.orchestration.pipeline import verify_submission
assert verify_submission('empty',[])['status']=='complete'
"""
    result=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True);assert result.returncode==0,result.stderr

def test_s3_configuration_is_supabase_compatible(monkeypatch):
    import boto3
    from app.storage import storage
    from app.config import settings
    seen={}
    monkeypatch.setattr(settings,'storage_backend','s3');monkeypatch.setattr(settings,'s3_bucket','private')
    class Client:
        def put_object(self,**args):seen.update(args)
    def client(*a,**kw):seen['addressing_style']=kw['config'].s3['addressing_style'];return Client()
    monkeypatch.setattr(boto3,'client',client)
    storage.put('12345678-1234-1234-1234-123456789abc',b'evidence')
    assert seen['addressing_style']=='path' and 'ServerSideEncryption' not in seen
