import io, json, hashlib, secrets
from datetime import timedelta, timezone, date
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select, func, delete
from sqlalchemy.exc import IntegrityError
from redis import Redis
from .models import *
from .db import get_db
from .security import current_user,require_role,access,audit,hasher,digest
from .schemas import *
from .config import settings
from .storage import storage
from .extraction import inspect_file,FIELDS
from .rules import RuleDefinition,LABEL
from .checklists import resolved_rules,config_lock
from .revisions import compare_runs
from .providers import SimulatedAuthority
from .worker import process_run

from .embedded import lifespan

app=FastAPI(lifespan=lifespan,title='ApprovalLens AI',version='1.0.0',docs_url='/api/v1/docs',openapi_url='/api/v1/openapi.json')
app.add_middleware(CORSMiddleware,allow_origins=[settings.allowed_origin],allow_credentials=True,allow_methods=['GET','POST','PUT','PATCH'],allow_headers=['Content-Type','X-CSRF-Token','Idempotency-Key'])
P='/api/v1'
BOUNDARY='ApprovalLens AI provides preliminary decision support. Official scrutiny, required inspections, and final regulatory decisions remain with competent authorities.'
@app.exception_handler(HTTPException)
async def http_error(_,exc): return JSONResponse({'error':{'message':exc.detail}},status_code=exc.status_code)
@app.exception_handler(RequestValidationError)
async def validation_error(_,exc): return JSONResponse({'error':{'message':'Invalid request','fields':[{'location':list(e['loc']),'message':e['msg']} for e in exc.errors()]}},status_code=422)
@app.exception_handler(IntegrityError)
async def conflict_error(_,exc): return JSONResponse({'error':{'message':'Conflicting or duplicate record; refresh and try again'}},status_code=409)
@app.middleware('http')
async def headers(request,call_next):
    if request.method in ('POST','PUT','PATCH'):
        try: length=int(request.headers.get('content-length','0'))
        except ValueError: return JSONResponse({'error':{'message':'Invalid Content-Length'}},status_code=400)
        if length>(settings.max_file_mb+1)*1024*1024: return JSONResponse({'error':{'message':'Request exceeds upload limit'}},status_code=413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff';response.headers['Cache-Control']='no-store'
    response.headers['Referrer-Policy']='same-origin'
    return response

def serialize(obj):
    return {c.name:getattr(obj,c.name) for c in obj.__table__.columns if c.name not in ('password_hash','storage_key','token_hash','csrf')}
def paged(db,q,offset,limit): return [serialize(x) for x in db.scalars(q.offset(offset).limit(limit)).all()]
def visible_query(user):
    q=select(Application)
    if user.role=='applicant': q=q.where(Application.institution_id.in_(select(Membership.institution_id).where(Membership.user_id==user.id)))
    elif user.role=='reviewer': q=q.where(Application.id.in_(select(Assignment.application_id).where(Assignment.user_id==user.id)))
    return q

def versions(db,app_id):
    result=[]
    for d in db.scalars(select(Document).where(Document.application_id==app_id)):
        v=db.scalar(select(DocumentVersion).where(DocumentVersion.document_id==d.id).order_by(DocumentVersion.version.desc()))
        if v: result.append((d,v))
    return result

def enqueue(db,user,a,key):
    if not 1<=len(key)<=64: raise HTTPException(422,'Idempotency-Key must be 1 to 64 characters')
    existing=db.scalar(select(ValidationRun).where(ValidationRun.application_id==a.id,ValidationRun.idempotency_key==key))
    if existing: return existing,False
    pending=db.scalar(select(ValidationRun).where(ValidationRun.application_id==a.id,ValidationRun.status.in_(['Queued','Extracting','Validating'])))
    if pending: raise HTTPException(409,'A processing run is already active')
    rs=db.scalar(select(RuleSet).where(RuleSet.active==True).order_by(RuleSet.version.desc()))
    snap=db.scalar(select(ReferenceSnapshot).order_by(ReferenceSnapshot.created_at.desc()))
    if not rs or not snap: raise HTTPException(409,'Administrator must configure a rule set and reference snapshot')
    rs,checklist_snapshot=resolved_rules(db,rs,a.category,a.reference_date)
    vs=versions(db,a.id); ids=[v.id for d,v in vs];inst=db.get(Institution,a.institution_id)
    corrections=[serialize(x) for x in db.scalars(select(Correction).where(Correction.version_id.in_(ids)).order_by(Correction.created_at))]
    # Serialize timestamps now so the immutable JSON snapshot is portable.
    for c in corrections: c['created_at']=c['created_at'].isoformat()
    run=ValidationRun(application_id=a.id,rule_set_id=rs.id,snapshot_id=snap.id,idempotency_key=key,input_snapshot={'version_ids':ids,'document_kinds':{v.id:d.kind for d,v in vs},'corrections':corrections,'checklists':checklist_snapshot, 'context':{'category':a.category,'declaration':a.declaration,'name':inst.name,'identifier':inst.identifier,'reference_date':a.reference_date,'intake':sum(p.intake for p in db.scalars(select(Programme).where(Programme.application_id==a.id)))}})
    db.add(run);db.flush();db.add(JobDispatch(run_id=run.id));audit(db,user,a.id,'validation_queued',{'run_id':run.id});return run,True

def dispatch(db,run):
    if settings.processing_mode=='embedded':
        # The committed database queue is polled by the in-service runner.
        return
    # Best-effort low-latency delivery; committed outbox survives process/broker failures.
    job=db.scalar(select(JobDispatch).where(JobDispatch.run_id==run.id))
    try:
        process_run.delay(run.id)
        if job:job.published_at=now();job.last_error=None;job.attempts+=1
    except Exception as exc:
        if job:job.last_error=type(exc).__name__+': dispatcher will retry';job.attempts+=1
    db.commit()


def document_bytes(key):
    try: return storage.get(key)
    except FileNotFoundError: raise HTTPException(410,'Original file removed by the retention operator; metadata and review history remain')

def version_access(db,user,version_id):
    v=db.get(DocumentVersion,version_id)
    if not v: raise HTTPException(404,'Document not found')
    d=db.get(Document,v.document_id); a=access(db,user,d.application_id)
    return v,d,a

def ensure_idle(db,a):
    if db.scalar(select(ValidationRun.id).where(ValidationRun.application_id==a.id,ValidationRun.status.in_(['Queued','Extracting','Validating']))): raise HTTPException(409,'Wait for the active validation run before changing evidence')

def editable(a):
    if a.status not in ('Draft','Clarification Requested'): raise HTTPException(409,'Evidence can only be changed in Draft or Clarification Requested')

def notify(db,a,message):
    users=set(db.scalars(select(Membership.user_id).where(Membership.institution_id==a.institution_id)))|set(db.scalars(select(Assignment.user_id).where(Assignment.application_id==a.id)))
    for user_id in users: db.add(Notification(user_id=user_id,application_id=a.id,message=message))

@app.get(P+'/health')
def health(): return {'status':'ok','model_assisted_extraction':'disabled','signature_verification':'not implemented','boundary':BOUNDARY,'demo_enabled':settings.demo_enabled}
@app.post(P+'/auth/login',response_model=AuthOut)
def login(body:Login,request:Request,response:Response,db=Depends(get_db)):
    if request.headers.get('origin') not in (None,settings.allowed_origin): raise HTTPException(403,'Origin not permitted')
    # Shared across API processes; fail closed when limiter is unavailable.
    try:
        redis=Redis.from_url(settings.redis_url,socket_connect_timeout=2,socket_timeout=2)
        ip=request.client.host if request.client else 'unknown'
        ip_key='login-ip:'+digest(ip)
        ip_count=redis.incr(ip_key)
        if ip_count==1: redis.expire(ip_key,900)
        if ip_count>100: raise HTTPException(429,'Too many attempts from this client; retry in 15 minutes')
        key='login:'+digest(ip+'|'+body.email.lower())
        count=redis.incr(key)
        if count==1: redis.expire(key,900)
        if count>10: raise HTTPException(429,'Too many attempts; try again in 15 minutes')
    except HTTPException: raise
    except Exception: raise HTTPException(503,'Authentication rate limiter unavailable; start Redis')
    user=db.scalar(select(User).where(User.email==body.email.lower()))
    valid=False
    try: valid=hasher.verify(user.password_hash if user else DUMMY_HASH,body.password)
    except Exception: pass
    if not valid or not user or not user.active: raise HTTPException(401,'Invalid email or password')
    token=secrets.token_urlsafe(48);csrf=secrets.token_urlsafe(32)
    db.add(Session(token_hash=digest(token),csrf=csrf,user_id=user.id,expires_at=now()+timedelta(hours=settings.session_hours)))
    audit(db,user,None,'login');db.commit()
    response.set_cookie('session',token,httponly=True,secure=settings.environment=='production',samesite='strict',max_age=settings.session_hours*3600,path='/')
    return {'user':serialize(user),'csrf':csrf}
DUMMY_HASH=hasher.hash('not-a-valid-account-password')
@app.get(P+'/auth/me',response_model=AuthOut)
def me(request:Request,user=Depends(current_user)):
    return {'user':serialize(user),'csrf':request.state.session.csrf}
@app.post(P+'/auth/logout')
def logout(request:Request,response:Response,user=Depends(current_user),db=Depends(get_db)):
    db.delete(db.get(Session,request.state.session.id));db.commit();response.delete_cookie('session',path='/');return {'ok':True}
@app.get(P+'/institutions')
def institutions(user=Depends(current_user),db=Depends(get_db)):
    q=select(Institution)
    if user.role!='administrator': q=q.where(Institution.id.in_(select(Membership.institution_id).where(Membership.user_id==user.id)))
    return paged(db,q,0,100)
@app.get(P+'/applications')
def applications(status:str|None=None,category:str|None=None,search:str='',severity:str|None=None,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),user=Depends(current_user),db=Depends(get_db)):
    q=visible_query(user).order_by(Application.created_at.desc())
    if status: q=q.where(Application.status==status)
    if category: q=q.where(Application.category==category)
    if search: q=q.where(Application.title.ilike('%'+search+'%') | Application.institution_id.in_(select(Institution.id).where(Institution.name.ilike('%'+search+'%'))))
    if severity:
        latest_id=select(ValidationRun.id).where(ValidationRun.application_id==Application.id).order_by(ValidationRun.created_at.desc()).limit(1).correlate(Application).scalar_subquery()
        matches=select(Finding.id).where(Finding.run_id==latest_id,Finding.severity==severity,Finding.result!='Passed',Finding.review_status.notin_(['Resolved','Dismissed with Reason']))
        if user.role=='applicant':matches=matches.where(Finding.released==True)
        q=q.where(matches.exists())
    total=db.scalar(select(func.count()).select_from(q.order_by(None).subquery()))
    rows=[]
    for a in db.scalars(q.offset(offset).limit(limit)):
        run=db.scalar(select(ValidationRun).where(ValidationRun.application_id==a.id).order_by(ValidationRun.created_at.desc()))
        fq=select(Finding).where(Finding.run_id==run.id,Finding.result!='Passed',Finding.review_status.notin_(['Resolved','Dismissed with Reason'])) if run else None
        if fq is not None and user.role=='applicant': fq=fq.where(Finding.released==True)
        fs=db.scalars(fq).all() if fq is not None else []
        if severity and not any(f.severity==severity for f in fs): continue
        rows.append({**serialize(a),'institution':db.get(Institution,a.institution_id).name,'processing_status':run.status if run else 'Not Started','open_findings':len(fs)})
    return {'items':rows,'offset':offset,'limit':limit,'total':total}
@app.post(P+'/applications',status_code=201,response_model=ApplicationOut)
def create_application(body:ApplicationIn,user=Depends(current_user),db=Depends(get_db)):
    require_role(user,'applicant')
    if not db.scalar(select(Membership).where(Membership.user_id==user.id,Membership.institution_id==body.institution_id)): raise HTTPException(403,'Institution membership required')
    if not db.scalar(select(ChecklistTemplate).where(ChecklistTemplate.category==body.category,ChecklistTemplate.active==True)): raise HTTPException(422,'Choose a configured category')
    a=Application(**body.model_dump(exclude={'programmes','reference_date'}),reference_date=body.reference_date.isoformat());db.add(a);db.flush()
    for p in body.programmes: db.add(Programme(application_id=a.id,**p.model_dump()))
    audit(db,user,a.id,'application_created');db.commit();return serialize(a)
@app.put(P+'/applications/{app_id}',response_model=ApplicationOut)
def save_application(app_id:str,body:ApplicationIn,user=Depends(current_user),db=Depends(get_db)):
    require_role(user,'applicant');a=access(db,user,app_id,True);editable(a);ensure_idle(db,a)
    if not db.scalar(select(ChecklistTemplate).where(ChecklistTemplate.category==body.category,ChecklistTemplate.active==True)): raise HTTPException(422,'Choose a configured category')
    if body.institution_id!=a.institution_id: raise HTTPException(422,'Institution cannot be changed')
    if a.status!='Draft' and (body.category!=a.category or body.reference_date.isoformat()!=a.reference_date): raise HTTPException(409,'Category and reference date are fixed after submission')
    a.title=body.title;a.category=body.category;a.reference_date=body.reference_date.isoformat();a.declaration=body.declaration
    db.execute(delete(Programme).where(Programme.application_id==a.id))
    for p in body.programmes: db.add(Programme(application_id=a.id,**p.model_dump()))
    audit(db,user,a.id,'draft_saved');db.commit();return serialize(a)
@app.get(P+'/applications/{app_id}')
def workspace(app_id:str,user=Depends(current_user),db=Depends(get_db)):
    a=access(db,user,app_id);runs=db.scalars(select(ValidationRun).where(ValidationRun.application_id==a.id).order_by(ValidationRun.created_at.desc())).all()
    docs=[]
    for d,v in versions(db,a.id):
        history=db.scalars(select(DocumentVersion).where(DocumentVersion.document_id==d.id).order_by(DocumentVersion.version.desc())).all()
        docs.append({**serialize(d),'versions':[{**serialize(x),'superseded':x.id!=v.id} for x in history]})
    fs=db.scalars(select(Finding).where(Finding.application_id==a.id).order_by(Finding.created_at.desc())).all()
    fs=[f for f in fs if user.role!='applicant' or f.released]
    threads=db.scalars(select(Clarification).where(Clarification.application_id==a.id).order_by(Clarification.created_at)).all()
    actions=db.scalars(select(ReviewerAction).where(ReviewerAction.application_id==a.id).order_by(ReviewerAction.created_at)).all() if user.role!='applicant' else []
    return {'application':serialize(a),'institution':serialize(db.get(Institution,a.institution_id)),'programmes':paged(db,select(Programme).where(Programme.application_id==a.id),0,100),'documents':docs,'runs':[serialize(r) for r in runs],'findings':[{**serialize(f),'evidence':paged(db,select(Evidence).where(Evidence.finding_id==f.id),0,100)} for f in fs],'clarifications':[{**serialize(t),'replies':paged(db,select(Reply).where(Reply.thread_id==t.id).order_by(Reply.created_at),0,100)} for t in threads],'verifications':paged(db,select(VerificationAttempt).where(VerificationAttempt.application_id==a.id).order_by(VerificationAttempt.created_at.desc()),0,100),'actions':[serialize(x) for x in actions]}
@app.post(P+'/applications/{app_id}/transition',response_model=ApplicationOut)
def transition(app_id:str,body:Transition,request:Request,user=Depends(current_user),db=Depends(get_db)):
    a=access(db,user,app_id,True)
    allowed={'applicant':{'Draft':['Submitted','Withdrawn'],'Clarification Requested':['Resubmitted','Withdrawn'],'Submitted':['Withdrawn'],'Resubmitted':['Withdrawn']},'reviewer':{'Submitted':['Under Review'],'Resubmitted':['Under Review'],'Under Review':['Preliminary Review Completed']}}
    if body.status not in allowed.get(user.role,{}).get(a.status,[]): raise HTTPException(409,'Workflow transition not allowed')
    run=None;created=False
    if body.status in ('Submitted','Resubmitted'):
        if not db.scalar(select(Programme).where(Programme.application_id==a.id)): raise HTTPException(422,'Declare at least one programme')
        run,created=enqueue(db,user,a,request.headers.get('idempotency-key') or uid())
    if body.status=='Preliminary Review Completed':
        latest=db.scalar(select(ValidationRun).where(ValidationRun.application_id==a.id).order_by(ValidationRun.created_at.desc()))
        if not latest or latest.status!='Completed': raise HTTPException(409,'Complete validation before concluding preliminary review')
        current_ids=[v.id for _,v in versions(db,a.id)]
        current_corrections=set(db.scalars(select(Correction.id).where(Correction.version_id.in_(current_ids))))
        pinned=latest.input_snapshot
        if set(current_ids)!=set(pinned['version_ids']) or current_corrections!={c['id'] for c in pinned.get('corrections',[])}: raise HTTPException(409,'Evidence or corrections changed; create a new validation run before completion')
        db.add(ReviewerAction(application_id=a.id,actor_id=user.id,action=body.status,reason=body.reason))
    a.status=body.status;audit(db,user,a.id,'workflow_changed',{'status':body.status,'reason':body.reason});notify(db,a,body.status);db.commit()
    if created: dispatch(db,run)
    return serialize(a)
@app.post(P+'/applications/{app_id}/documents',status_code=201,response_model=DocumentVersionOut)
async def upload(app_id:str,file:UploadFile=File(...),kind:str=Form(...),document_id:str|None=Form(None),user=Depends(current_user),db=Depends(get_db)):
    require_role(user,'applicant');a=access(db,user,app_id,True);editable(a);ensure_idle(db,a)
    if (db.scalar(select(func.count()).select_from(DocumentVersion).join(Document).where(Document.application_id==a.id)) or 0)>=settings.max_document_versions: raise HTTPException(422,'Application document-version limit reached')
    if kind not in ['certificate','infrastructure','floor_plan','photograph','other']: raise HTTPException(422,'Unsupported document type')
    data=await file.read(settings.max_file_mb*1024*1024+1)
    try: pages=inspect_file(data,file.filename or '',file.content_type)
    except ValueError as exc: raise HTTPException(422,str(exc))
    if document_id:
        d=db.get(Document,document_id)
        if not d or d.application_id!=a.id: raise HTTPException(404,'Document not found')
        # Kind is immutable for existing document; corrections are recorded separately.
        if d.kind!=kind: raise HTTPException(422,'Use the existing document type for replacement')
    else: d=Document(application_id=a.id,kind=kind);db.add(d);db.flush()
    n=db.scalar(select(func.max(DocumentVersion.version)).where(DocumentVersion.document_id==d.id)) or 0
    v=DocumentVersion(document_id=d.id,version=n+1,filename=Path(file.filename or 'document').name[:255],storage_key=uid(),sha256=hashlib.sha256(data).hexdigest(),mime=file.content_type,pages=pages,uploaded_by=user.id)
    storage.put(v.storage_key,data);db.add(v);db.flush();audit(db,user,a.id,'document_version_uploaded',{'version_id':v.id,'version':v.version});db.commit()
    return serialize(v)
@app.get(P+'/documents/{version_id}/download')
def download(version_id:str,user=Depends(current_user),db=Depends(get_db)):
    v,d,a=version_access(db,user,version_id)
    return Response(document_bytes(v.storage_key),media_type=v.mime,headers={'Content-Disposition':f'inline; filename="document-{v.id}.{ "pdf" if v.mime=="application/pdf" else "png" if v.mime=="image/png" else "jpg"}"','Content-Security-Policy':"sandbox"})
@app.get(P+'/documents/{version_id}/preview/{page}')
def preview(version_id:str,page:int,user=Depends(current_user),db=Depends(get_db)):
    v,d,a=version_access(db,user,version_id)
    if not 1<=page<=v.pages: raise HTTPException(404,'Page not found')
    raw=document_bytes(v.storage_key)
    if v.mime=='application/pdf':
        import pymupdf as fitz
        with fitz.open(stream=raw,filetype='pdf') as pdf: raw=pdf[page-1].get_pixmap(matrix=fitz.Matrix(1.2,1.2),alpha=False).tobytes('png')
        return Response(raw,media_type='image/png')
    return Response(raw,media_type=v.mime)
@app.get(P+'/documents/{version_id}/fields')
def fields(version_id:str,user=Depends(current_user),db=Depends(get_db)):
    v,d,a=version_access(db,user,version_id)
    vals=paged(db,select(ExtractedField).where(ExtractedField.version_id==v.id).order_by(ExtractedField.page),0,500)
    return {'fields':vals,'unknown_fields':[k for k in FIELDS if k not in {f['name'] for f in vals}],'corrections':paged(db,select(Correction).where(Correction.version_id==v.id).order_by(Correction.created_at),0,500),'validity':document_validity(db,v,a)}
def document_validity(db,v,a):
    f=db.scalar(select(ExtractedField).where(ExtractedField.version_id==v.id,ExtractedField.name=='expiry_date'))
    if not f: return 'Validity Unknown' if db.get(Document,v.document_id).kind=='certificate' else 'Not Applicable'
    try: return 'Expired' if date.fromisoformat(f.value)<date.fromisoformat(a.reference_date) else 'Valid for Reference Date'
    except ValueError: return 'Validity Unknown'
@app.post(P+'/documents/{version_id}/corrections')
def correction(version_id:str,body:CorrectionIn,user=Depends(current_user),db=Depends(get_db)):
    require_role(user,'applicant','reviewer');v,d,a=version_access(db,user,version_id)
    a=access(db,user,a.id,True);ensure_idle(db,a)
    if user.role=='applicant': editable(a)
    elif a.status not in ('Under Review','Clarification Requested'): raise HTTPException(409,'Corrections require an active review')
    if body.name not in FIELDS: raise HTTPException(422,'Unknown field')
    if body.name=='document_type' and body.value not in ('certificate','infrastructure','floor_plan','photograph','other'): raise HTTPException(422,'Choose a supported document type')
    c=Correction(version_id=v.id,actor_id=user.id,**body.model_dump());db.add(c);audit(db,user,a.id,'field_correction_recorded',{'version_id':v.id,'field':body.name});db.commit();return serialize(c)
@app.post(P+'/applications/{app_id}/runs',response_model=RunOut)
def revalidate(app_id:str,request:Request,user=Depends(current_user),db=Depends(get_db)):
    a=access(db,user,app_id,True)
    if a.status in ('Withdrawn','Preliminary Review Completed'): raise HTTPException(409,'Application is closed')
    run,created=enqueue(db,user,a,request.headers.get('idempotency-key') or uid());db.commit()
    if created: dispatch(db,run)
    return serialize(run)
@app.post(P+'/runs/{run_id}/retry',response_model=RunOut)
def retry(run_id:str,user=Depends(current_user),db=Depends(get_db)):
    r=db.scalar(select(ValidationRun).where(ValidationRun.id==run_id).with_for_update())
    if not r: raise HTTPException(404,'Run not found')
    a=access(db,user,r.application_id,True)
    if a.status in ('Withdrawn','Preliminary Review Completed'): raise HTTPException(409,'Application is closed')
    if db.scalar(select(ValidationRun.id).where(ValidationRun.application_id==a.id,ValidationRun.id!=r.id,ValidationRun.status.in_(['Queued','Extracting','Validating']))): raise HTTPException(409,'Another run is active')
    if db.scalar(select(ValidationRun.id).where(ValidationRun.application_id==a.id,ValidationRun.created_at>r.created_at)): raise HTTPException(409,'Retry the latest run or create a new run; older runs stay historical')
    if r.status in ('Extracting','Validating','Queued') and r.heartbeat.replace(tzinfo=timezone.utc)<now()-timedelta(minutes=15): r.status='Failed'
    if r.status!='Failed': raise HTTPException(409,'Only failed or stale runs may be retried')
    if r.attempts>=6: raise HTTPException(409,'Retry limit reached; replace evidence and create a new run')
    r.status='Queued';r.stage='Retry queued';r.heartbeat=now()
    job=db.scalar(select(JobDispatch).where(JobDispatch.run_id==r.id))
    if job:job.published_at=None
    else:db.add(JobDispatch(run_id=r.id))
    audit(db,user,a.id,'validation_retry_requested',{'run_id':r.id});db.commit();dispatch(db,r);return serialize(r)
@app.post(P+'/findings/{finding_id}/review')
def review(finding_id:str,body:ActionIn,user=Depends(current_user),db=Depends(get_db)):
    require_role(user,'reviewer');f=db.get(Finding,finding_id)
    if not f: raise HTTPException(404,'Finding not found')
    a=access(db,user,f.application_id)
    if a.status not in ('Under Review','Clarification Requested'): raise HTTPException(409,'Start review first')
    f.review_status=body.status;f.released=body.release
    db.add(ReviewerAction(application_id=a.id,finding_id=f.id,actor_id=user.id,action=body.status,reason=body.reason));audit(db,user,a.id,'finding_reviewed',{'finding_id':f.id,'status':body.status});db.commit();return serialize(f)
@app.post(P+'/applications/{app_id}/clarifications')
def clarify(app_id:str,body:ClarificationIn,user=Depends(current_user),db=Depends(get_db)):
    require_role(user,'reviewer');a=access(db,user,app_id,True)
    if a.status not in ('Under Review','Clarification Requested'): raise HTTPException(409,'Start review before requesting clarification')
    for fid in body.finding_ids:
        f=db.get(Finding,fid)
        if not f or f.application_id!=a.id: raise HTTPException(422,'Finding does not belong to application')
        f.review_status='Clarification Requested';f.released=True
    t=Clarification(application_id=a.id,actor_id=user.id,**body.model_dump());db.add(t);a.status='Clarification Requested';audit(db,user,a.id,'clarification_requested');notify(db,a,'Clarification requested');db.commit();return serialize(t)
@app.post(P+'/clarifications/{thread_id}/replies')
def reply(thread_id:str,body:ReplyIn,user=Depends(current_user),db=Depends(get_db)):
    require_role(user,'applicant','reviewer');t=db.get(Clarification,thread_id)
    if not t: raise HTTPException(404,'Thread not found')
    a=access(db,user,t.application_id)
    if a.status not in ('Clarification Requested','Under Review'): raise HTTPException(409,'Thread cannot be updated in current workflow')
    r=Reply(thread_id=t.id,actor_id=user.id,text=body.text);db.add(r);audit(db,user,a.id,'clarification_replied');notify(db,a,'Clarification reply received');db.commit();return serialize(r)
@app.post(P+'/documents/{version_id}/verify')
def verify(version_id:str,body:VerificationIn,user=Depends(current_user),db=Depends(get_db)):
    require_role(user,'reviewer');v,d,a=version_access(db,user,version_id)
    if body.provider_id=='manual':
        if not all([body.source,body.reference,body.observation]): raise HTTPException(422,'Provide source, reference and observation')
        detail={'mode':'manual','method':'Reviewer source consultation','source_reference':body.source,'reference':body.reference,'observation':body.observation,'request_timestamp':now().isoformat(),'matched_fields':[],'mismatched_fields':[],'outcome':body.outcome}
    elif d.kind!='certificate': detail={'mode':'simulated','outcome':'Not Supported','reason':'Provider only supports certificates'}
    else:
        fs={}
        for f in db.scalars(select(ExtractedField).where(ExtractedField.version_id==v.id)):
            fs[f.name]=f.value if f.name not in fs or fs[f.name]==f.value else None
        snap=db.scalar(select(ReferenceSnapshot).order_by(ReferenceSnapshot.created_at.desc()))
        config=db.scalar(select(ProviderConfig).where(ProviderConfig.provider_id==body.provider_id))
        detail=SimulatedAuthority().verify(fs,snap.records if snap else {},config.available if config else False)
        detail['snapshot_id']=snap.id if snap else None
    attempt=VerificationAttempt(application_id=a.id,version_id=v.id,actor_id=user.id,provider_id=body.provider_id,outcome=detail['outcome'],details=detail);db.add(attempt);audit(db,user,a.id,'source_verification_recorded',{'version_id':v.id});db.commit();return serialize(attempt)
@app.post(P+'/applications/{app_id}/infrastructure/annotations')
def annotate(app_id:str,body:NoteIn,user=Depends(current_user),db=Depends(get_db)):
    require_role(user,'reviewer');a=access(db,user,app_id)
    r=ReviewerAction(application_id=a.id,actor_id=user.id,action=body.action,reason=body.reason);db.add(r);audit(db,user,a.id,'infrastructure_annotation');db.commit();return serialize(r)
@app.get(P+'/applications/{app_id}/audit')
def app_audit(app_id:str,offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),user=Depends(current_user),db=Depends(get_db)):
    access(db,user,app_id)
    rows=paged(db,select(AuditEvent).where(AuditEvent.application_id==app_id).order_by(AuditEvent.created_at.desc()),offset,limit)
    if user.role=='applicant':
        for row in rows: row['details']={k:v for k,v in row['details'].items() if k!='reason'}
    return rows
@app.get(P+'/dashboard')
def dashboard(user=Depends(current_user),db=Depends(get_db)):
    apps=db.scalars(visible_query(user)).all();ids=[a.id for a in apps]
    latest=[db.scalar(select(ValidationRun).where(ValidationRun.application_id==a.id).order_by(ValidationRun.created_at.desc())) for a in apps]
    run_ids=[r.id for r in latest if r]
    q=select(Finding).where(Finding.run_id.in_(run_ids),Finding.result!='Passed',Finding.review_status.notin_(['Resolved','Dismissed with Reason']))
    if user.role=='applicant': q=q.where(Finding.released==True)
    findings=db.scalars(q).all()
    return {'applications':len(apps),'open_findings':len(findings),'clarification_requested':sum(a.status=='Clarification Requested' for a in apps),'processing':sum(bool(r and r.status in ('Queued','Extracting','Validating')) for r in latest),'notifications':paged(db,select(Notification).where(Notification.user_id==user.id).order_by(Notification.created_at.desc()),0,10)}
@app.get(P+'/checklists')
def checklists(user=Depends(current_user),db=Depends(get_db)):
    return [{**serialize(c),'items':paged(db,select(ChecklistItem).where(ChecklistItem.template_id==c.id),0,100),'disclosure':LABEL} for c in db.scalars(select(ChecklistTemplate).where(ChecklistTemplate.active==True))]
@app.get(P+'/admin/{resource}')
def admin_list(resource:str,search:str='',offset:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=100),user=Depends(current_user),db=Depends(get_db)):
    require_role(user,'administrator')
    models={'applications':Application,'users':User,'institutions':Institution,'assignments':Assignment,'rules':RuleSet,'rule-versions':RuleVersion,'audit':AuditEvent,'providers':ProviderConfig,'snapshots':ReferenceSnapshot,'checklists':ChecklistTemplate}
    if resource not in models: raise HTTPException(404,'Resource not found')
    model=models[resource];q=select(model).order_by(model.created_at.desc())
    if resource=='audit' and search: q=q.where(AuditEvent.event.ilike('%'+search+'%'))
    return paged(db,q,offset,limit)
@app.post(P+'/admin/institutions')
def institution_create(body:InstitutionIn,user=Depends(current_user),db=Depends(get_db)):
    require_role(user,'administrator');i=Institution(**body.model_dump());db.add(i);audit(db,user,None,'institution_created');db.commit();return serialize(i)
@app.post(P+'/admin/users')
def user_create(body:UserIn,user=Depends(current_user),db=Depends(get_db)):
    require_role(user,'administrator')
    if len(body.password)<12: raise HTTPException(422,'Password requires at least 12 characters')
    if body.role=='applicant' and not db.get(Institution,body.institution_id): raise HTTPException(422,'Applicant needs a valid institution')
    u=User(email=body.email.lower(),password_hash=hasher.hash(body.password),role=body.role);db.add(u);db.flush()
    if body.institution_id: db.add(Membership(user_id=u.id,institution_id=body.institution_id))
    audit(db,user,None,'user_created',{'user_id':u.id});db.commit();return serialize(u)
@app.post(P+'/admin/assignments')
def assignment_create(body:AssignmentIn,user=Depends(current_user),db=Depends(get_db)):
    require_role(user,'administrator');r=db.get(User,body.user_id)
    if not r or r.role!='reviewer' or not db.get(Application,body.application_id): raise HTTPException(422,'Choose a valid reviewer and application')
    a=Assignment(**body.model_dump());db.add(a);audit(db,user,body.application_id,'reviewer_assigned');db.commit();return serialize(a)
@app.post(P+'/admin/rules')
def rules_create(body:list[RuleDefinition],user=Depends(current_user),db=Depends(get_db)):
    require_role(user,'administrator');config_lock(db)
    if not body or len(body)>100 or len({r.rule_id for r in body})!=len(body): raise HTTPException(422,'Provide 1–100 unique rule IDs')
    rs=RuleSet(name='Illustrative prototype rules',version=(db.scalar(select(func.max(RuleSet.version))) or 0)+1,active=False);db.add(rs);db.flush()
    for r in body: db.add(RuleVersion(rule_set_id=rs.id,rule_id=r.rule_id,version=r.version,definition=r.model_dump(mode='json')))
    audit(db,user,None,'rule_set_created',{'rule_set_id':rs.id});db.commit();return serialize(rs)
@app.post(P+'/admin/rules/{rule_set_id}/activate')
def activate(rule_set_id:str,user=Depends(current_user),db=Depends(get_db)):
    require_role(user,'administrator');config_lock(db);rs=db.get(RuleSet,rule_set_id)
    if not rs: raise HTTPException(404,'Rule set not found')
    if rs.name.startswith('resolved-'): raise HTTPException(409,'Resolved run bundles cannot be activated; activate an administrator rule set')
    for x in db.scalars(select(RuleSet).with_for_update()): x.active=x.id==rs.id
    audit(db,user,None,'rule_set_activated',{'rule_set_id':rs.id});db.commit();return serialize(rs)
@app.post(P+'/admin/providers/{provider_id}')
def provider_config(provider_id:str,available:bool,user=Depends(current_user),db=Depends(get_db)):
    require_role(user,'administrator');p=db.scalar(select(ProviderConfig).where(ProviderConfig.provider_id==provider_id))
    if not p: raise HTTPException(404,'Provider not found')
    p.available=available;audit(db,user,None,'provider_configured');db.commit();return serialize(p)
@app.post(P+'/admin/checklists')
def checklist_create(body:ChecklistIn,user=Depends(current_user),db=Depends(get_db)):
    require_role(user,'administrator');config_lock(db)
    old=db.scalars(select(ChecklistTemplate).where(ChecklistTemplate.category==body.category)).all()
    for c in old: c.active=False
    c=ChecklistTemplate(category=body.category,version=max([x.version for x in old],default=0)+1);db.add(c);db.flush()
    for kind in body.kinds: db.add(ChecklistItem(template_id=c.id,kind=kind,description=LABEL))
    audit(db,user,None,'checklist_created');db.commit();return serialize(c)
@app.get(P+'/applications/{app_id}/report')
def report(app_id:str,user=Depends(current_user),db=Depends(get_db)):
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from xml.sax.saxutils import escape
    a=access(db,user,app_id);info=workspace(app_id,user,db);buff=io.BytesIO();styles=getSampleStyleSheet();parts=[]
    def p(text,style='BodyText'): parts.append(Paragraph(escape(str(text)),styles[style]));parts.append(Spacer(1,8))
    p('ApprovalLens AI | Preliminary validation report','Title');p(BOUNDARY);p('Independent prototype. No official endorsement or regulatory certification.');p(f'Generated (UTC): {now().isoformat()}');p(f'{a.title} | {a.status}');p(f'Institution: {info["institution"]["name"]}; reference date: {a.reference_date}')
    p('Model-assisted extraction disabled. Signature verification not implemented. Severity is review priority, not a fraud probability.')
    for run in info['runs']:
        p(f'Run {run["id"]} | {run["status"]}','Heading2');p(f'Rule set: {run["rule_set_id"]}; reference snapshot: {run["snapshot_id"]}')
        for f in info['findings']:
            if f['run_id']!=run['id']: continue
            p(f'{f["title"]}: {f["result"]} / {f["severity"]} / {f["review_status"]}','Heading3');p(f'Rule {f["rule_id"]} v{f["rule_version"]}; finding {f["id"]}; {f["comparison"]}');p(f['explanation']);p(f'Observed: {json.dumps(f["observed"])}; Expected: {json.dumps(f["expected"])}')
            for e in f['evidence']: p(f'Evidence: version {e["version_id"] or "missing"}, page {e["page"] or "N/A"}; checklist {e["requirement"] or "N/A"}. {e["excerpt"]}')
            p(f['next_action']);p(f['limitations'])
    for d in info['documents']:
        for v in d['versions']: p(f'Document: {v["filename"]}, version {v["version"]}, SHA-256 {v["sha256"]}, superseded: {v["superseded"]}; validity: {document_validity(db,db.get(DocumentVersion,v["id"]),a)}')
    for v in info['verifications']: p(f'Verification: {v["outcome"]}; {json.dumps(v["details"])}')
    for t in info['clarifications']:
        p('Clarification: '+t['question'])
        for r in t['replies']: p('Reply: '+r['text'])
    for action in info['actions']: p(f'Reviewer action: {action["action"]}; actor {action["actor_id"]}; {action["created_at"]}; {action["reason"]}')
    if user.role!='applicant':
        p('Cross-document evidence analysis','Heading2')
        for analysis in db.scalars(select(EvidenceAnalysis).where(EvidenceAnalysis.application_id==a.id)):
            data=analysis.result
            p('Run '+analysis.run_id+' | '+analysis.pipeline_version+' | '+data.get('status','unknown'))
            p(data.get('calibration_note','No calibrated probability available.'))
            for item in data.get('findings',[]):
                p(item['explanation'])
                p('Status: '+item['status']+' | Evidence: '+', '.join(item['evidence_ids']))
                for claim in data.get('claims',[]):
                    if claim['claim_id'] in item['claim_ids']:
                        p('Document '+claim['document_id']+' page '+str(claim['source_page'])+': '+claim['field_name']+' = '+claim['raw_value'])
    if user.role=='applicant': p('This applicant report contains released findings only. Reviewer-only observations are omitted.')
    SimpleDocTemplate(buff).build(parts);audit(db,user,a.id,'report_exported');db.commit()
    return Response(buff.getvalue(),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="ApprovalLens-report.pdf"'})

@app.post(P+'/admin/users/{user_id}/active')
def toggle_user(user_id:str,active:bool,user=Depends(current_user),db=Depends(get_db)):
    require_role(user,'administrator')
    if user_id==user.id: raise HTTPException(409,'Cannot deactivate your own account')
    target=db.get(User,user_id)
    if not target: raise HTTPException(404,'User not found')
    target.active=active
    if not active: db.execute(delete(Session).where(Session.user_id==user_id))
    audit(db,user,None,'user_active_changed',{'user_id':user_id,'active':active});db.commit();return serialize(target)
@app.post(P+'/admin/rules/{rule_set_id}/deactivate')
def deactivate(rule_set_id:str,user=Depends(current_user),db=Depends(get_db)):
    require_role(user,'administrator');config_lock(db);rs=db.get(RuleSet,rule_set_id)
    if not rs: raise HTTPException(404,'Rule set not found')
    rs.active=False;audit(db,user,None,'rule_set_deactivated',{'rule_set_id':rs.id});db.commit();return serialize(rs)

@app.get(P+'/applications/{app_id}/comparison')
def comparison(app_id:str,run_id:str|None=None,user=Depends(current_user),db=Depends(get_db)):
    access(db,user,app_id)
    q=select(ValidationRun).where(ValidationRun.application_id==app_id,ValidationRun.status=='Completed')
    if run_id:q=q.where(ValidationRun.id==run_id)
    run=db.scalar(q.order_by(ValidationRun.created_at.desc()))
    if not run:raise HTTPException(404,'No completed validation run to compare')
    return compare_runs(db,run,user.role=='applicant')

@app.get(P+'/ready')
def readiness(db=Depends(get_db)):
    from sqlalchemy import text
    try:
        db.execute(text('SELECT 1'))
        Redis.from_url(settings.redis_url,socket_connect_timeout=2,socket_timeout=2).ping()
    except Exception:raise HTTPException(503,'Database or queue unavailable')
    return {'status':'ready'}

# Evidence research results are reviewer-only, matching unreleased scrutiny privacy.
def stored_evidence(db,user,app_id,run_id=None):
    access(db,user,app_id);require_role(user,'reviewer','administrator')
    q=select(ValidationRun).where(ValidationRun.application_id==app_id)
    if run_id:q=q.where(ValidationRun.id==run_id)
    run=db.scalar(q.order_by(ValidationRun.created_at.desc()))
    if not run:raise HTTPException(404,'No validation run yet')
    analysis=db.scalar(select(EvidenceAnalysis).where(EvidenceAnalysis.run_id==run.id))
    if not analysis:raise HTTPException(409,'Evidence analysis not available for this run. Complete a new validation run.')
    import copy
    result=copy.deepcopy(analysis.result)
    for f in result.get('findings',[]):
        f['reviews']=[]
        for event in db.scalars(select(AuditEvent).where(AuditEvent.application_id==app_id,AuditEvent.event=='cross_document_reviewed').order_by(AuditEvent.created_at)):
            if event.details.get('run_id')==run.id and event.details.get('finding_id')==f['finding_id']:
                f['reviews'].append({'status':event.details['status'],'reason':event.details['reason'],'at':event.created_at.isoformat(),'user_id':event.actor_id})
        if f['reviews']:f['reviewed_status']=f['reviews'][-1]['status']
    return result

@app.get(P+'/applications/{app_id}/evidence-graph')
def evidence_graph(app_id:str,run_id:str|None=None,user=Depends(current_user),db=Depends(get_db)):
    r=stored_evidence(db,user,app_id,run_id);return {'graph':r.get('graph'),'status':r['status'],'run_id':r['run_id']}

@app.get(P+'/applications/{app_id}/cross-document-findings')
def cross_document_findings(app_id:str,run_id:str|None=None,user=Depends(current_user),db=Depends(get_db)):
    return stored_evidence(db,user,app_id,run_id)

@app.get(P+'/applications/{app_id}/claims')
def evidence_claims(app_id:str,run_id:str|None=None,user=Depends(current_user),db=Depends(get_db)):
    r=stored_evidence(db,user,app_id,run_id);return {'claims':r['claims'],'run_id':r['run_id']}

from pydantic import BaseModel,Field
from typing import Literal
class EvidenceReviewInput(BaseModel):
    run_id:str
    finding_id:str
    status:Literal['Acknowledged','Clarification Requested','Resolved','Dismissed with Reason']
    reason:str=Field(min_length=3,max_length=4000)

@app.post(P+'/applications/{app_id}/cross-document-findings/review')
def review_evidence(app_id:str,body:EvidenceReviewInput,user=Depends(current_user),db=Depends(get_db)):
    result=stored_evidence(db,user,app_id,body.run_id)
    a=access(db,user,app_id)
    if a.status in ('Withdrawn','Preliminary Review Completed'):raise HTTPException(409,'Application is closed')
    if not any(f['finding_id']==body.finding_id for f in result['findings']):raise HTTPException(404,'Finding not found in this run')
    audit(db,user,app_id,'cross_document_reviewed',body.model_dump());db.commit();return {'status':body.status}
