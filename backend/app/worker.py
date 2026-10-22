from datetime import date
from celery import Celery
from sqlalchemy import select, delete
from .config import settings
from .db import SessionLocal
from .models import *
from .storage import storage
from .extraction import extract
from .rules import evaluate
celery=Celery('approvallens',broker=settings.redis_url)
celery.conf.update(task_acks_late=True,task_reject_on_worker_lost=True,worker_prefetch_multiplier=1,task_soft_time_limit=540,task_time_limit=600,broker_connection_retry_on_startup=True,broker_connection_timeout=3,task_publish_retry=False,broker_transport_options={'socket_connect_timeout':3,'socket_timeout':3})

def run_pipeline(run_id):
    with SessionLocal() as db:
        run=db.scalar(select(ValidationRun).where(ValidationRun.id==run_id).with_for_update())
        if not run or run.status in ('Completed','Extracting','Validating'): return
        if run.attempts>=6:
            run.status='Failed';run.error='Retry limit reached. Replace evidence and create a new run.';db.commit();return
        run.status='Extracting'; run.attempts+=1; run.heartbeat=now(); db.commit()
        try:
            application=db.get(Application,run.application_id)
            if application.status=='Withdrawn':
                run.status='Failed';run.stage='Application withdrawn';run.error='Withdrawn applications are not processed';db.commit();return
            docs=[]
            for i,version_id in enumerate(run.input_snapshot['version_ids']):
                v=db.get(DocumentVersion,version_id)
                run.stage=f'Extracting document {i+1} of {len(run.input_snapshot["version_ids"])}';run.heartbeat=now();db.commit()
                pages=db.scalars(select(PageText).where(PageText.version_id==v.id)).all()
                if not pages:
                    raw,fields=extract(storage.get(v.storage_key),v.mime)
                    for p in raw: db.add(PageText(version_id=v.id,**p))
                    for f in fields: db.add(ExtractedField(version_id=v.id,**f))
                    db.commit()
                    pages=db.scalars(select(PageText).where(PageText.version_id==v.id)).all()
                fields={}
                for f in db.scalars(select(ExtractedField).where(ExtractedField.version_id==v.id).order_by(ExtractedField.page)):
                    item={'value':f.value,'page':f.page,'bbox':f.bbox,'excerpt':f.excerpt}
                    if f.name in fields and fields[f.name]['value']!=f.value:
                        item['value']=None;item['bbox']=None
                        item['excerpt']='Conflicting page values: '+fields[f.name]['excerpt']+' | '+f.excerpt
                    fields[f.name]=item
                for correction in run.input_snapshot.get('corrections',[]):
                    if correction['version_id']==v.id:
                        original=fields.get(correction['name'],{})
                        fields[correction['name']]={'value':correction['value'],'page':original.get('page',1),'bbox':original.get('bbox'),'excerpt':f"Recorded correction: {correction['value']} (reason: {correction['reason']}). Original: {original.get('value','unknown')}"}
                detected=(fields.get('document_type',{}).get('value') or '').lower()
                kind=detected if detected in ('certificate','infrastructure','floor_plan','photograph','other') else run.input_snapshot['document_kinds'][v.id]
                docs.append({'id':v.id,'kind':kind,'sha256':v.sha256,'fields':fields,'text':'\n'.join(p.text for p in pages)})
            run.status='Validating';run.stage='Applying pinned illustrative rules';run.heartbeat=now();db.commit()
            # One transaction for all findings: retries cannot leave duplicate partial results.
            old_ids=db.scalars(select(Finding.id).where(Finding.run_id==run.id)).all()
            if old_ids:
                db.execute(delete(Evidence).where(Evidence.finding_id.in_(old_ids)))
                db.execute(delete(Finding).where(Finding.run_id==run.id))
            prev=db.scalar(select(ValidationRun).where(ValidationRun.application_id==application.id,ValidationRun.status=='Completed',ValidationRun.created_at<run.created_at).order_by(ValidationRun.created_at.desc()))
            previous={f.rule_id:f.result for f in db.scalars(select(Finding).where(Finding.run_id==prev.id))} if prev else {}
            context={**run.input_snapshot['context'],'references':db.get(ReferenceSnapshot,run.snapshot_id).records}
            for rv in db.scalars(select(RuleVersion).where(RuleVersion.rule_set_id==run.rule_set_id)):
                rule=rv.definition
                if not rule['active'] or rule['category'] not in ('*',run.input_snapshot['context'].get('category',application.category)): continue
                ref=context['reference_date']
                if ref<rule['effective_from'] or (rule.get('effective_to') and ref>rule['effective_to']): continue
                out=evaluate(rule,docs,context); evidence=out.pop('evidence')
                f=Finding(application_id=application.id,run_id=run.id,rule_version_id=rv.id,rule_id=rv.rule_id,rule_version=rv.version,**out,comparison='Unchanged' if previous.get(rv.rule_id)==out['result'] else 'Changed' if rv.rule_id in previous else 'New')
                db.add(f);db.flush()
                for e in evidence: db.add(Evidence(finding_id=f.id,**e))
            from .evidence_bridge import analyze_run
            analysis=analyze_run(db,run)
            existing=db.scalar(select(EvidenceAnalysis).where(EvidenceAnalysis.run_id==run.id))
            if existing: db.delete(existing);db.flush()
            db.add(EvidenceAnalysis(run_id=run.id,application_id=application.id,pipeline_version=analysis['pipeline_version'],result=analysis))
            run.status='Completed';run.stage='Extraction and validation completed';run.error=None;run.heartbeat=now()
            db.add(AuditEvent(application_id=application.id,event='validation_completed',details={'run_id':run.id}))
            db.commit()
        except Exception as exc:
            db.rollback(); run=db.get(ValidationRun,run_id);run.status='Failed';run.stage='Processing failed; safe retry available';run.error=f'{type(exc).__name__}: file processing failed. Check worker dependencies or replace unreadable evidence.';run.heartbeat=now();db.commit()
            raise
@celery.task(bind=True,max_retries=2,default_retry_delay=10)
def process_run(self,run_id):
    try: run_pipeline(run_id)
    except Exception as exc: raise self.retry(exc=RuntimeError(type(exc).__name__)) from None
