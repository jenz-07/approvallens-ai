import hashlib,secrets
from datetime import timezone
from fastapi import Depends,HTTPException,Request
from sqlalchemy import select
from argon2 import PasswordHasher
from .db import get_db
from .models import *
from .config import settings
hasher=PasswordHasher()
def digest(token): return hashlib.sha256(token.encode()).hexdigest()
def current_user(request:Request,db=Depends(get_db)):
    token=request.cookies.get('session','')
    s=db.scalar(select(Session).where(Session.token_hash==digest(token))) if token else None
    if not s or s.expires_at.replace(tzinfo=timezone.utc)<now(): raise HTTPException(401,'Sign in required or session expired')
    user=db.get(User,s.user_id)
    if not user or not user.active: raise HTTPException(401,'Account unavailable')
    if request.method not in ('GET','HEAD','OPTIONS'):
        if not secrets.compare_digest(request.headers.get('x-csrf-token',''),s.csrf): raise HTTPException(403,'CSRF token missing or invalid')
        if request.headers.get('origin') not in (None,settings.allowed_origin): raise HTTPException(403,'Origin not permitted')
    request.state.session=s
    return user

def require_role(user,*roles):
    if user.role not in roles: raise HTTPException(403,'Role not permitted')
def access(db,user,app_id,lock=False):
    query=select(Application).where(Application.id==app_id)
    app=db.scalar(query.with_for_update() if lock else query)
    if not app: raise HTTPException(404,'Application not found')
    if user.role=='administrator': return app
    if user.role=='applicant': allowed=db.scalar(select(Membership).where(Membership.user_id==user.id,Membership.institution_id==app.institution_id))
    else: allowed=db.scalar(select(Assignment).where(Assignment.user_id==user.id,Assignment.application_id==app.id))
    if not allowed: raise HTTPException(404,'Application not found')
    return app

def audit(db,user,app_id,event,details=None):
    db.add(AuditEvent(actor_id=user.id,application_id=app_id,event=event,details=details or {}))
