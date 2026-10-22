"""Evidence-first run comparison: no new decisions and no model output."""
from sqlalchemy import select
from .models import ValidationRun,Finding,Evidence,DocumentVersion

FLAGGED={'Failed','Review Needed','Insufficient Evidence'}
def compare_runs(db,current,applicant=False):
    previous=db.scalar(select(ValidationRun).where(ValidationRun.application_id==current.application_id,ValidationRun.status=='Completed',ValidationRun.created_at<current.created_at).order_by(ValidationRun.created_at.desc()))
    def findings(run):
        if not run:return {}
        q=select(Finding).where(Finding.run_id==run.id)
        if applicant:q=q.where(Finding.released==True)
        return {f.rule_id:f for f in db.scalars(q)}
    before,after=findings(previous),findings(current)
    rows=[]
    for rid in sorted(set(before)|set(after)):
        old,new=before.get(rid),after.get(rid)
        if not old:change='New'
        elif not new:change='No current visible evaluation'
        elif old.result in FLAGGED and new.result=='Passed':change='Improved'
        elif old.result=='Passed' and new.result in FLAGGED:change='Regressed'
        elif old.result!=new.result or old.observed!=new.observed or old.expected!=new.expected:change='Changed'
        else:change='Unchanged'
        f=new or old
        ev=list(db.scalars(select(Evidence).where(Evidence.finding_id==f.id)))
        rows.append({'rule_id':rid,'title':f.title,'change':change,'previous_result':old.result if old else None,'current_result':new.result if new else None,'previous_observed':old.observed if old else None,'current_observed':new.observed if new else None,'finding_id':f.id,'run_id':f.run_id,'evidence':[{'version_id':e.version_id,'page':e.page,'bbox':e.bbox,'excerpt':e.excerpt,'requirement':e.requirement} for e in ev]})
    prev_ids=set(previous.input_snapshot.get('version_ids',[])) if previous else set()
    cur_ids=set(current.input_snapshot.get('version_ids',[]))
    return {'run_id':current.id,'previous_run_id':previous.id if previous else None,'rule_set_changed':bool(previous and previous.rule_set_id!=current.rule_set_id),'reference_snapshot_changed':bool(previous and previous.snapshot_id!=current.snapshot_id),'documents_added':sorted(cur_ids-prev_ids),'documents_superseded':sorted(prev_ids-cur_ids),'summary':{k:sum(r['change']==k for r in rows) for k in ('New','Improved','Regressed','Changed','Unchanged','No current visible evaluation')},'rules':rows,'limitations':'Computed from visible stored evidence and result changes. Improved means an illustrative check now passes, not regulatory approval. Rule/reference changes may explain differences.'}
