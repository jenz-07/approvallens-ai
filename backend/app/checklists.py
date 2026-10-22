"""Compile pinned checklist requirements into an immutable resolved rule set."""
import hashlib,json
from sqlalchemy import select,func,text
from .models import RuleSet,RuleVersion,ChecklistTemplate,ChecklistItem
from .rules import RuleDefinition

def config_lock(db):
    if db.bind.dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock(620261022)'))

def resolved_rules(db,base,category,reference_date):
    config_lock(db)
    templates=list(db.scalars(select(ChecklistTemplate).where(ChecklistTemplate.category==category,ChecklistTemplate.active==True)))
    snapshot=[{'id':c.id,'version':c.version,'items':[i.kind for i in db.scalars(select(ChecklistItem).where(ChecklistItem.template_id==c.id))]} for c in templates]
    rules=list(db.scalars(select(RuleVersion).where(RuleVersion.rule_set_id==base.id)))
    covered={r.definition.get('required_document') for r in rules if r.definition['active'] and r.definition['check_type'] in ('required_document','infrastructure') and r.definition['category'] in ('*',category) and r.definition['effective_from']<=reference_date and (not r.definition.get('effective_to') or r.definition['effective_to']>=reference_date)}
    missing={k for c in snapshot for k in c['items']}-covered
    if not missing:return base,snapshot
    key='resolved-'+hashlib.sha256(json.dumps([base.id,category,snapshot,sorted(missing)],sort_keys=True).encode()).hexdigest()
    target=db.scalar(select(RuleSet).where(RuleSet.name==key))
    if not target:
        target=RuleSet(name=key,version=(db.scalar(select(func.max(RuleSet.version))) or 0)+1,active=False);db.add(target);db.flush()
        for r in rules:db.add(RuleVersion(rule_set_id=target.id,rule_id=r.rule_id,version=r.version,definition=r.definition))
        for kind in sorted(missing):
            definition=RuleDefinition(rule_id='checklist-'+kind+'-'+hashlib.sha256(key.encode()).hexdigest()[:8],version=1,title='Checklist evidence: '+kind,description='Compiled from pinned illustrative checklist',category=category,required_document=kind,check_type='required_document',explanation='The selected illustrative checklist requires this evidence type.').model_dump(mode='json')
            db.add(RuleVersion(rule_set_id=target.id,rule_id=definition['rule_id'],version=1,definition=definition))
    return target,snapshot
