from datetime import date
from difflib import SequenceMatcher
import re
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict

LABEL='Illustrative prototype rule — not an official AICTE requirement.'
class RuleDefinition(BaseModel):
    model_config=ConfigDict(extra='forbid')
    rule_id: str = Field(min_length=1, max_length=100)
    version: int = Field(ge=1)
    title: str = Field(max_length=200)
    description: str = Field(max_length=2000)
    category: str = '*'
    required_document: str | None = None
    field: str | None = None
    check_type: Literal['required_document','required_field','expiry','date_order','identifier','name','reference','intake','duplicate','infrastructure','infrastructure_declaration','similarity','cross_document']
    parameters: dict = Field(default_factory=dict)
    severity: Literal['High','Medium','Low'] = 'Medium'
    explanation: str = Field(max_length=2000)
    source_reference: Literal['Illustrative prototype rule — not an official AICTE requirement.'] = LABEL
    effective_from: date = date(2020,1,1)
    effective_to: date | None = None
    demonstration_only: Literal[True] = True
    active: bool = True

def normalize(x): return re.sub(r'[^a-z0-9]', '', (x or '').lower())
def evaluate(rule, docs, context):
    """Pure, allowlisted engine. docs contain only authorized, pinned versions."""
    r=RuleDefinition.model_validate(rule)
    selected=[d for d in docs if not r.required_document or d['kind']==r.required_document]
    evidence=[]; observed={}; expected={}; result='Passed'
    def add(d,field=None):
        f=d.get('fields',{}).get(field,{}) if field else {}
        evidence.append({'version_id':d['id'],'page':f.get('page',1),'bbox':f.get('bbox'),'excerpt':f.get('excerpt','File identity / declared document type'),'requirement':None})
    def value(d,key): return d.get('fields',{}).get(key,{}).get('value')
    if r.check_type in ('required_document','infrastructure'):
        expected={'document':r.required_document}
        observed={'count':len(selected)}
        if not selected:
            result='Failed'; evidence=[{'version_id':None,'page':None,'bbox':None,'excerpt':'No submitted evidence','requirement':r.required_document}]
        else:
            for d in selected: add(d)
    elif r.check_type=='infrastructure_declaration':
        rooms=context.get('declaration',{}).get('rooms')
        expected={'declaration':'Nonempty rooms list with name and nonnegative integer declared_capacity; illustrative schema only'}
        if not isinstance(rooms,list) or not rooms: result='Insufficient Evidence'
        elif any(not isinstance(room,dict) or not isinstance(room.get('name'),str) or not room['name'].strip() or type(room.get('declared_capacity')) is not int or room['declared_capacity']<0 for room in rooms): result='Failed'
        observed={'rooms':rooms}
        evidence=[{'version_id':None,'page':None,'bbox':None,'excerpt':'Applicant structured facility declaration, not independently verified','requirement':'facility-declaration'}]
    elif r.check_type=='cross_document':
        conflicts={}
        for key in ('institution_identifier','institution_name'):
            vals=[(d,value(d,key)) for d in docs if value(d,key)]
            if len({normalize(v) for _,v in vals})>1:
                conflicts[key]=[v for _,v in vals]
                for d,_ in vals: add(d,key)
        observed={'conflicts':conflicts}
        if conflicts: result='Review Needed'
        elif len([d for d in docs if value(d,'institution_identifier')])<2: result='Not Evaluated'
    elif r.check_type=='duplicate':
        groups={}
        for d in docs: groups.setdefault(d['sha256'],[]).append(d)
        dup=[d for g in groups.values() if len(g)>1 for d in g]
        if dup: result='Review Needed'
        observed={'duplicate_versions':len(dup)}
        for d in dup: add(d)
    elif r.check_type=='similarity':
        pairs=[]
        for i,a in enumerate(docs):
            for b in docs[i+1:]:
                if a['sha256']!=b['sha256'] and a.get('text') and b.get('text'):
                    score=SequenceMatcher(None,a['text'][:10000],b['text'][:10000],autojunk=True).ratio()
                    if score >= .9: pairs.append([a['id'],b['id']]); add(a); add(b)
        observed={'similar_pairs':pairs}
        if pairs: result='Review Needed'
        elif len(docs)<2: result='Not Evaluated'
    elif not selected:
        result='Insufficient Evidence'; expected={'document':r.required_document}
        evidence=[{'version_id':None,'page':None,'bbox':None,'excerpt':'Required source document missing','requirement':r.required_document or r.rule_id}]
    else:
        failures=[]; missing=[]; values=[]
        for d in selected:
            field=r.field or {'expiry':'expiry_date','date_order':'issue_date','identifier':'institution_identifier','name':'institution_name','reference':'reference_number','intake':'intake'}.get(r.check_type,'')
            v=value(d,field); values.append(v); add(d,field)
            if v is None: missing.append(d['id']); continue
            if r.check_type=='required_field': pass
            elif r.check_type=='expiry':
                try:
                    if date.fromisoformat(v)<date.fromisoformat(context['reference_date']): failures.append('Expired')
                except ValueError: failures.append('Invalid date')
                expected={'valid_on':context['reference_date']}
            elif r.check_type=='date_order':
                end=value(d,'expiry_date')
                try:
                    if not end: missing.append(d['id'])
                    elif date.fromisoformat(v)>date.fromisoformat(end): failures.append('Issue date after expiry')
                except ValueError: failures.append('Invalid date')
            elif r.check_type in ('identifier','name'):
                target=context['identifier' if r.check_type=='identifier' else 'name']; expected={'value':target}
                if normalize(v)!=normalize(target): failures.append('Mismatch requires review')
            elif r.check_type in ('reference','intake'):
                record=context['references'].get(value(d,'reference_number') or '')
                if not record: missing.append(d['id'])
                elif r.check_type=='reference':
                    expected={'identifier':record.get('institution_identifier')}
                    if not value(d,'institution_identifier'): missing.append(d['id'])
                    elif value(d,'institution_identifier') != record.get('institution_identifier'): failures.append('Reference record conflicts with identifier')
                else:
                    expected={'intake':record.get('intake')}
                    try:
                        if record.get('intake') is None: missing.append(d['id'])
                        elif int(v)!=int(record['intake']) or context['intake'] != int(record['intake']): failures.append('Declared/document intake differs from reference')
                    except (ValueError,TypeError): failures.append('Invalid intake')
        observed={'values':values,'issues':failures,'missing_version_ids':missing}
        if failures: result='Failed'
        elif missing: result='Insufficient Evidence'
    return dict(title=r.title,severity=r.severity,result=result,observed=observed,expected=expected,explanation=r.explanation, next_action='Review evidence and request clarification if necessary.' if result!='Passed' else 'Check source evidence before relying on this result.', limitations=LABEL+' Deterministic parsing may miss fields. Similarity can reflect shared templates; it is not evidence of misconduct.',evidence=evidence)
