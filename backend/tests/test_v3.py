from datetime import timedelta
from sqlalchemy import select
from app.db import SessionLocal
from app.models import *
from app.extraction import parse_fields
from app.checklists import resolved_rules
from app.main import enqueue,dispatch
from app.dispatcher import tick
from app.worker import run_pipeline
from .conftest import sign_in
from .test_workflow import payload

def test_parser_keeps_blank_labels_unknown_and_conflicts_explicit():
    fields=parse_fields([{'page':1,'method':'native_pdf','words':[],'text':'Institution Name:   \nReference Number: A\nInstitution ID: ONE\nInstitution Identifier: TWO\nValid Until: 2028-01-01'}])
    values={f['name']:f for f in fields}
    assert 'institution_name' not in values
    assert values['reference_number']['value']=='A'
    assert values['institution_identifier']['value'] is None
    assert 'Conflicting' in values['institution_identifier']['excerpt']
    assert values['expiry_date']['value']=='2028-01-01'

def test_checklist_compilation_preserves_active_base(client):
    with SessionLocal() as db:
        base=db.scalar(select(RuleSet).where(RuleSet.active==True))
        checklist=ChecklistTemplate(category='Additional evidence example',version=1,active=True);db.add(checklist);db.flush()
        db.add(ChecklistItem(template_id=checklist.id,kind='floor_plan',description='Illustrative'));db.flush()
        resolved,snapshot=resolved_rules(db,base,checklist.category,'2026-07-01');db.flush()
        assert resolved.id!=base.id and not resolved.active and base.active
        assert snapshot[0]['items']==['floor_plan']
        assert any(r.definition.get('required_document')=='floor_plan' for r in db.scalars(select(RuleVersion).where(RuleVersion.rule_set_id==resolved.id)))
        again,_=resolved_rules(db,base,checklist.category,'2026-07-01');assert again.id==resolved.id
        db.rollback()

def test_outbox_recovers_broker_failure_and_worker_lease(client,monkeypatch):
    import app.main as main
    sign_in(client)
    aid=client.post('/api/v1/applications',json=payload(client,'Outbox recovery')).json()['id']
    with SessionLocal() as db:
        a=db.get(Application,aid);u=db.scalar(select(User).where(User.email=='applicant@demo.local'))
        run,_=enqueue(db,u,a,'outbox-test');rid=run.id;db.commit()
        def fail(*args,**kwargs):raise ConnectionError('Synthetic failure')
        monkeypatch.setattr(main.process_run,'delay',fail)
        dispatch(db,run)
        assert db.get(ValidationRun,rid).status=='Queued'
        assert db.scalar(select(JobDispatch).where(JobDispatch.run_id==rid)).last_error
    calls=[];monkeypatch.setattr(main.process_run,'delay',lambda x:calls.append(x))
    tick();assert rid in calls
    with SessionLocal() as db:
        run=db.get(ValidationRun,rid);run.status='Extracting';run.attempts=1;run.heartbeat=now()-timedelta(minutes=20);db.commit()
    tick()
    with SessionLocal() as db:assert db.get(ValidationRun,rid).status=='Queued'
    run_pipeline(rid);run_pipeline(rid)
    with SessionLocal() as db:
        assert db.get(ValidationRun,rid).status=='Completed'
        fs=list(db.scalars(select(Finding).where(Finding.run_id==rid)))
        assert len(fs)==len(set(f.rule_id for f in fs))

def test_severity_filter_is_applied_before_pagination(client):
    sign_in(client,'reviewer')
    full=client.get('/api/v1/applications?severity=High&limit=100').json()
    first=client.get('/api/v1/applications?severity=High&limit=1').json()
    assert first['total']==len(full['items'])
    assert len(first['items'])==min(1,first['total'])
