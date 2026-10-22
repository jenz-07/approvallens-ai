"""Operator CLI: remove expired sessions and orphaned local blobs only.
Submitted evidence is not silently deleted. See docs/OPERATIONS.md for retention.
"""
import argparse
from datetime import timedelta
from pathlib import Path
from sqlalchemy import select,delete
from .db import SessionLocal
from .models import *
from .config import settings
from .storage import storage

def cleanup(apply=False):
    cutoff=now()-timedelta(days=settings.retention_days)
    with SessionLocal() as db:
        eligible=db.scalars(select(Application).where(Application.status.in_(['Withdrawn','Preliminary Review Completed']),Application.created_at<cutoff)).all()
        # Explicit closed-application blob retention. All metadata, checksums and history remain.
        for a in eligible:
            for v in db.scalars(select(DocumentVersion).join(Document).where(Document.application_id==a.id)):
                print('Eligible retained blob:',v.id)
                if apply:
                    storage.delete(v.storage_key)
                    db.add(AuditEvent(application_id=a.id,event='retention_blob_deleted',details={'version_id':v.id,'retention_days':settings.retention_days}))
        expired=db.scalars(select(Session).where(Session.expires_at<now())).all()
        print('Expired sessions:',len(expired),'Closed applications eligible:',len(eligible),'Apply:',apply)
        if apply:
            for s in expired: db.delete(s)
            db.commit()
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args();cleanup(args.apply)
