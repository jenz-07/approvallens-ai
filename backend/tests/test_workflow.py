from datetime import timedelta
import io,hashlib
from sqlalchemy import select,func
from app.models import *
from app.db import SessionLocal
from app.seed import synthetic_pdf
from app.worker import run_pipeline
from app.main import enqueue
from app.extraction import inspect_file
from app.rules import evaluate,RuleDefinition
from app.providers import SimulatedAuthority
from app.security import hasher
from .conftest import sign_in

def payload(client,title='Workflow integration'):
    inst=client.get('/api/v1/institutions').json()[0]
    return {'institution_id':inst['id'],'title':title,'category':'Extension of Approval','reference_date':'2026-07-01','programmes':[{'name':'Synthetic Engineering','intake':60}],'declaration':{'rooms':[{'name':'A','declared_capacity':60}]}}
def upload(client,app_id,data,document_id=None,filename='random.pdf',mime='application/pdf',kind='certificate'):
    return client.post(f'/api/v1/applications/{app_id}/documents',data={'kind':kind,**({'document_id':document_id} if document_id else {})},files={'file':(filename,data,mime)})
def cert(identifier='SYN-001',expiry='2025-01-01'):
    return synthetic_pdf(['Institution Name: Synthetic Institute of Technology',f'Institution Identifier: {identifier}','Reference Number: CERT-001','Issue Date: 2024-01-01',f'Expiry Date: {expiry}','Intake: 60'])
def workspace(client,aid): return client.get('/api/v1/applications/'+aid).json()

def test_complete_vertical_slice_and_history(client):
    sign_in(client)
    r=client.post('/api/v1/applications',json=payload(client));assert r.status_code==201,r.text
    aid=r.json()['id'];v1=upload(client,aid,cert()).json()
    with SessionLocal() as db:
        reviewer=db.scalar(select(User).where(User.role=='reviewer'));db.add(Assignment(application_id=aid,user_id=reviewer.id));db.commit()
    r=client.post(f'/api/v1/applications/{aid}/transition',json={'status':'Submitted','reason':'Ready for preliminary review'});assert r.status_code==200,r.text
    first=workspace(client,aid)['runs'][0];run_pipeline(first['id'])
    assert upload(client,aid,cert()).status_code==409
    assert not workspace(client,aid)['findings'] # unreleased findings are private
    sign_in(client,'reviewer')
    assert client.post(f'/api/v1/applications/{aid}/transition',json={'status':'Under Review','reason':'Begin review'}).status_code==200
    w=workspace(client,aid);f=next(f for f in w['findings'] if f['rule_id']=='expiry');assert f['result']=='Failed'
    assert f['evidence'][0]['page']==1 and '2025' in f['evidence'][0]['excerpt']
    t=client.post(f'/api/v1/applications/{aid}/clarifications',json={'finding_ids':[f['id']],'question':'Please upload a current certificate.'});assert t.status_code==200
    sign_in(client)
    assert client.post('/api/v1/clarifications/'+t.json()['id']+'/replies',json={'text':'Uploaded a replacement.'}).status_code==200
    doc_id=v1['document_id'];v2=upload(client,aid,cert(expiry='2027-01-01'),doc_id).json();assert v2['version']==2
    assert client.post(f'/api/v1/applications/{aid}/transition',json={'status':'Resubmitted','reason':'New evidence submitted'}).status_code==200
    second=workspace(client,aid)['runs'][0];assert second['id']!=first['id'];run_pipeline(second['id'])
    sign_in(client,'reviewer');w=workspace(client,aid)
    assert len(w['runs'])==2
    old=next(x for x in w['findings'] if x['id']==f['id']);assert old['result']=='Failed';assert old['review_status']=='Clarification Requested'
    new=next(x for x in w['findings'] if x['run_id']==second['id'] and x['rule_id']=='expiry');assert new['result']=='Passed';assert new['comparison']=='Changed'
    assert w['documents'][0]['versions'][1]['superseded']
    comparison=client.get(f'/api/v1/applications/{aid}/comparison?run_id={second["id"]}').json()
    assert comparison['previous_run_id']==first['id']
    assert next(x for x in comparison['rules'] if x['rule_id']=='expiry')['change']=='Improved'
    assert v1['id'] in comparison['documents_superseded']
    assert client.post(f'/api/v1/applications/{aid}/transition',json={'status':'Under Review','reason':'Review replacement'}).status_code==200
    assert client.post('/api/v1/findings/'+new['id']+'/review',json={'status':'Resolved','reason':'Current expiry inspected','release':True}).status_code==200
    assert client.post(f'/api/v1/applications/{aid}/transition',json={'status':'Preliminary Review Completed','reason':'Preliminary review complete; authority decision remains external'}).status_code==200
    report=client.get(f'/api/v1/applications/{aid}/report');assert report.status_code==200 and report.content.startswith(b'%PDF')
    import pymupdf as fitz
    with fitz.open(stream=report.content,filetype='pdf') as pdf:
        text=''.join(p.get_text() for p in pdf);assert 'preliminary decision support' in text and 'expiry' in text
    assert hashlib.sha256(client.get('/api/v1/documents/'+v1['id']+'/download').content).hexdigest()==v1['sha256']

def test_tenant_isolation_and_download_authorization(client):
    sign_in(client);aid=client.get('/api/v1/applications').json()['items'][0]['id'];w=workspace(client,aid);vid=w['documents'][0]['versions'][0]['id']
    with SessionLocal() as db:
        i=Institution(name='Other synthetic tenant',identifier='OTHER');db.add(i);db.flush()
        u=User(email='other@demo.local',role='applicant',password_hash=hasher.hash('DemoOnly!2026'));db.add(u);db.flush();db.add(Membership(institution_id=i.id,user_id=u.id));db.commit()
    sign_in(client,'other')
    for path in [f'/applications/{aid}',f'/documents/{vid}/download',f'/documents/{vid}/preview/1',f'/documents/{vid}/fields',f'/applications/{aid}/report',f'/applications/{aid}/audit']:
        assert client.get('/api/v1'+path).status_code==404,path
    assert client.get('/api/v1/applications').json()['items']==[]
    assert client.get('/api/v1/admin/users').status_code==403

def test_csrf_logout_expiry_and_rate_limit(client):
    sign_in(client);del client.headers['X-CSRF-Token']
    assert client.post('/api/v1/applications',json=payload(client)).status_code==403
    me=client.get('/api/v1/auth/me').json();client.headers['X-CSRF-Token']=me['csrf']
    assert client.post('/api/v1/auth/logout').status_code==200
    assert client.get('/api/v1/auth/me').status_code==401
    sign_in(client)
    with SessionLocal() as db:
        for s in db.scalars(select(Session)):s.expires_at=now()-timedelta(hours=1)
        db.commit()
    assert client.get('/api/v1/auth/me').status_code==401
    for _ in range(11):r=client.post('/api/v1/auth/login',json={'email':'missing@demo.local','password':'bad'})
    assert r.status_code==429

def test_unassigned_reviewer_and_role_mutation(client):
    sign_in(client);aid=client.post('/api/v1/applications',json=payload(client,'Unassigned')).json()['id']
    sign_in(client,'reviewer');assert client.get('/api/v1/applications/'+aid).status_code==404
    assert client.post('/api/v1/admin/institutions',json={'name':'X','identifier':'X'}).status_code==403

def test_upload_rejections_and_password_pdf(client):
    sign_in(client);aid=client.post('/api/v1/applications',json=payload(client,'Upload limits')).json()['id']
    assert upload(client,aid,b'<script>bad</script>').status_code==422
    assert upload(client,aid,cert(),filename='fake.png',mime='image/png').status_code==422
    assert upload(client,aid,b'x'*(16*1024*1024)).status_code in (413,422)
    import pymupdf as fitz
    d=fitz.open();d.new_page();encrypted=d.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256,user_pw='secret',owner_pw='owner');d.close()
    r=upload(client,aid,encrypted);assert r.status_code==422 and 'Password-protected' in r.text

def test_actual_ocr_seed_and_scenarios(client):
    with SessionLocal() as db:
        apps=db.scalars(select(Application).where(Application.title.like('0%'))).all();assert len(apps)==6
        results={a.title[:2]:{f.rule_id:f.result for f in db.scalars(select(Finding).where(Finding.application_id==a.id))} for a in apps}
        assert results['01']['identifier']=='Passed'
        assert results['02']['required-certificate']=='Failed'
        assert results['03']['expiry']=='Failed'
        assert results['04']['identifier']=='Failed'
        assert results['05']['duplicate']=='Review Needed'
        a=next(a for a in apps if a.title.startswith('06'))
        fields=db.scalars(select(ExtractedField).join(DocumentVersion,ExtractedField.version_id==DocumentVersion.id).join(Document).where(Document.application_id==a.id,ExtractedField.method=='tesseract')).all()
        assert any(f.name=='reference_number' and f.value=='CERT-006' for f in fields)
        assert db.scalar(select(VerificationAttempt).where(VerificationAttempt.application_id==a.id)).outcome=='Source Unavailable'

def test_rules_insufficient_evidence_invalid_dates_and_no_eval():
    r=RuleDefinition(rule_id='test',version=1,title='test',description='test',check_type='expiry',required_document='certificate',explanation='test').model_dump(mode='json')
    assert evaluate(r,[],{'reference_date':'2026-07-01'})['result']=='Insufficient Evidence'
    doc={'id':'x','kind':'certificate','fields':{'expiry_date':{'value':'2026-99-40','page':1}}}
    assert evaluate(r,[doc],{'reference_date':'2026-07-01'})['result']=='Failed'
    import pytest
    with pytest.raises(ValueError):RuleDefinition.model_validate({**r,'check_type':'__import__("os")'})

def test_provider_unknown_mismatch_and_independent_validity():
    p=SimulatedAuthority();records={'ABC':{'institution_identifier':'SYN-1'}}
    assert p.verify({'reference_number':'unknown'},records)['outcome']=='Verification Pending'
    assert p.verify({'reference_number':'ABC','institution_identifier':'WRONG'},records)['outcome']=='Mismatch Detected'
    assert p.verify({'reference_number':'ABC','institution_identifier':'SYN-1','expiry_date':'2000-01-01'},records)['outcome']=='Verified'
    assert p.verify({},records,False)['outcome']=='Source Unavailable'

def test_idempotency_and_pinned_rules(client):
    sign_in(client);aid=client.post('/api/v1/applications',json=payload(client,'Pinned')).json()['id'];upload(client,aid,cert())
    header={'Idempotency-Key':'retry-same-operation'}
    first=client.post('/api/v1/applications/'+aid+'/runs',headers=header).json()
    again=client.post('/api/v1/applications/'+aid+'/runs',headers=header).json();assert first['id']==again['id']
    run_pipeline(first['id']);run_pipeline(first['id'])
    with SessionLocal() as db:
        count=db.scalar(select(func.count()).select_from(Finding).where(Finding.run_id==first['id']));assert count==13
        old=db.get(ValidationRun,first['id']);old_id=old.rule_set_id
    sign_in(client,'admin')
    rules=client.get('/api/v1/admin/rule-versions').json();body=[rules[0]['definition']];body[0]['version']=2
    new=client.post('/api/v1/admin/rules',json=body);assert new.status_code==200,new.text
    assert client.post('/api/v1/admin/rules/'+new.json()['id']+'/activate').status_code==200
    with SessionLocal() as db:assert db.get(ValidationRun,first['id']).rule_set_id==old_id
    # restore seed version for remaining tests
    assert client.post('/api/v1/admin/rules/'+old_id+'/activate').status_code==200

def test_failed_worker_is_visible_and_retry_does_not_duplicate(client,monkeypatch):
    sign_in(client);aid=client.post('/api/v1/applications',json=payload(client,'Retry')).json()['id'];upload(client,aid,cert())
    rid=client.post('/api/v1/applications/'+aid+'/runs').json()['id']
    import app.worker as worker
    original=worker.extract
    monkeypatch.setattr(worker,'extract',lambda *args:(_ for _ in ()).throw(RuntimeError('Synthetic failure')))
    import pytest
    with pytest.raises(RuntimeError):run_pipeline(rid)
    assert workspace(client,aid)['runs'][0]['status']=='Failed'
    monkeypatch.setattr(worker,'extract',original)
    assert client.post('/api/v1/runs/'+rid+'/retry').status_code==200
    run_pipeline(rid);run_pipeline(rid)
    with SessionLocal() as db:
        assert db.get(ValidationRun,rid).status=='Completed'
        assert db.scalar(select(func.count()).select_from(Finding).where(Finding.run_id==rid))==13

def test_correction_is_separate_and_runs_snapshot_inputs(client):
    sign_in(client);aid=client.post('/api/v1/applications',json=payload(client,'Correction')).json()['id'];v=upload(client,aid,cert()).json()
    rid=client.post('/api/v1/applications/'+aid+'/runs').json()['id'];run_pipeline(rid)
    r=client.post('/api/v1/documents/'+v['id']+'/corrections',json={'name':'expiry_date','value':'2027-01-01','reason':'Applicant documented correction'})
    assert r.status_code==200
    fields=client.get('/api/v1/documents/'+v['id']+'/fields').json()
    assert next(f for f in fields['fields'] if f['name']=='expiry_date')['value']=='2025-01-01'
    next_id=client.post('/api/v1/applications/'+aid+'/runs').json()['id'];run_pipeline(next_id)
    with SessionLocal() as db:
        assert db.get(ValidationRun,rid).input_snapshot['corrections']==[]
        assert len(db.get(ValidationRun,next_id).input_snapshot['corrections'])==1
        assert db.scalar(select(Finding).where(Finding.run_id==rid,Finding.rule_id=='expiry')).result=='Failed'
        assert db.scalar(select(Finding).where(Finding.run_id==next_id,Finding.rule_id=='expiry')).result=='Passed'

def test_new_draft_dashboard_and_manual_verification(client):
    sign_in(client);aid=client.post('/api/v1/applications',json=payload(client,'New draft statistics')).json()['id']
    assert client.get('/api/v1/dashboard').status_code==200
    v=upload(client,aid,cert()).json()
    assert client.post('/api/v1/documents/'+v['id']+'/verify',json={'provider_id':'manual','source':'Synthetic source','reference':'X','observation':'Checked','outcome':'Verified'}).status_code==403
    with SessionLocal() as db:
        r=db.scalar(select(User).where(User.role=='reviewer'));db.add(Assignment(application_id=aid,user_id=r.id));db.commit()
    sign_in(client,'reviewer')
    assert client.post('/api/v1/documents/'+v['id']+'/verify',json={'provider_id':'manual'}).status_code==422
    result=client.post('/api/v1/documents/'+v['id']+'/verify',json={'provider_id':'manual','source':'Synthetic source','reference':'X','observation':'Checked reference','outcome':'Manual Review Required'})
    assert result.status_code==200 and result.json()['details']['mode']=='manual'

def test_structured_facility_rules():
    rule=RuleDefinition(rule_id='rooms',version=1,title='Rooms',description='Demonstration',check_type='infrastructure_declaration',explanation='Schema only').model_dump(mode='json')
    assert evaluate(rule,[],{'declaration':{}})['result']=='Insufficient Evidence'
    assert evaluate(rule,[],{'declaration':{'rooms':[{'name':'A','declared_capacity':-1}]}})['result']=='Failed'
    assert evaluate(rule,[],{'declaration':{'rooms':[{'name':'A','declared_capacity':5}]}})['result']=='Passed'


def test_evaluation_script_matches_seeded_ground_truth(client,capsys,monkeypatch):
    import json,sys
    from app import evaluate
    monkeypatch.setattr(sys,'argv',['evaluate'])
    evaluate.main()
    out=json.loads(capsys.readouterr().out)
    assert out['dataset_applications']==6 and out['finding_precision']==1.0 and out['finding_recall']==1.0
    assert out['field_exact_match']['correct']==out['field_exact_match']['total']>0
    assert all(v['expected']==v['observed'] for v in out['simulated_verification'])
