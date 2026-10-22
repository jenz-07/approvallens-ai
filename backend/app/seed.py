"""Explicit demo seed. Reference date 2026-07-01; all dates synthetic and stable."""
import io,hashlib,json
from pathlib import Path
import pymupdf as fitz
from PIL import Image,ImageDraw,ImageFont
from sqlalchemy import select,delete
from .models import *
from .db import SessionLocal
from .config import settings
from .security import hasher
from .storage import storage
from .rules import RuleDefinition,LABEL
from .main import enqueue
from .worker import run_pipeline

REFERENCE_DATE='2026-07-01'
def synthetic_pdf(lines):
    doc=fitz.open();p=doc.new_page()
    p.insert_text((45,45),'SYNTHETIC DEMONSTRATION MATERIAL',fontsize=16)
    y=85
    for line in lines: p.insert_text((45,y),line,fontsize=11);y+=22
    data=doc.tobytes();doc.close();return data

def seed():
    if not settings.demo_enabled or settings.environment=='production': raise RuntimeError('Set DEMO_ENABLED=true in development only')
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email=='admin@demo.local')):
            print('Demo already seeded; no changes');return
        inst=Institution(name='Synthetic Institute of Technology',identifier='SYN-001',address='100 Example Avenue, Demo City');db.add(inst);db.flush()
        users={}
        for role,name in [('applicant','applicant'),('reviewer','reviewer'),('administrator','admin')]:
            u=User(email=f'{name}@demo.local',password_hash=hasher.hash('DemoOnly!2026'),role=role);db.add(u);db.flush();users[role]=u
        db.add(Membership(user_id=users['applicant'].id,institution_id=inst.id))
        rs=RuleSet(name='Illustrative prototype checks',version=1,active=True);db.add(rs);db.flush()
        specs=[('required-certificate','Required certificate','required_document','certificate',None),('required-infrastructure','Infrastructure evidence presence','infrastructure','infrastructure',None),('identifier-present','Institution identifier present','required_field','certificate','institution_identifier'),('expiry','Certificate reference-date validity','expiry','certificate',None),('dates','Date ordering','date_order','certificate',None),('identifier','Institution identifier consistency','identifier','certificate',None),('name','Normalized institution name comparison','name','certificate',None),('reference','Certificate reference consistency','reference','certificate',None),('intake','Submitted intake versus reference','intake','certificate',None),('duplicate','Exact duplicate files','duplicate',None,None),('similarity','Text similarity review aid','similarity',None,None),('facility-declaration','Structured facility declaration','infrastructure_declaration',None,None),('cross-document','Conflicting document fields','cross_document',None,None)]
        for rid,title,check,kind,field in specs:
            r=RuleDefinition(rule_id=rid,version=1,title=title,description=title,check_type=check,required_document=kind,field=field,explanation=title+'. '+LABEL,severity='High' if check in ('expiry','identifier') else 'Low' if check=='similarity' else 'Medium')
            db.add(RuleVersion(rule_set_id=rs.id,rule_id=rid,version=1,definition=r.model_dump(mode='json')))
        registry={f'CERT-{i:03}':{'institution_identifier':'SYN-001','institution_name':inst.name,'intake':'60'} for i in range(1,7)}
        registry['CERT-006']['unavailable']=True
        db.add(ReferenceSnapshot(label='Synthetic authority registry 2026-07-01 v1',records=registry));db.add(ProviderConfig(provider_id='synthetic-authority',available=True))
        for category in ('Extension of Approval','Change in Intake'):
            c=ChecklistTemplate(category=category,version=1);db.add(c);db.flush()
            for kind in ('certificate','infrastructure'): db.add(ChecklistItem(template_id=c.id,kind=kind,description=LABEL))
        names=['Consistent submission','Missing certificate','Expired certificate','Conflicting identifiers','Duplicate evidence','Unavailable source + scanned certificate']
        ground_truth=[];run_ids=[]
        for i,title in enumerate(names,1):
            a=Application(institution_id=inst.id,title=f'{i:02} · {title}',category='Extension of Approval',reference_date=REFERENCE_DATE,status='Submitted',declaration={'rooms':[{'name':'Teaching room A','declared_capacity':60}],'note':'Self-declared; not independently measured'})
            db.add(a);db.flush();db.add(Programme(application_id=a.id,name='Synthetic Engineering',intake=60));db.add(Assignment(application_id=a.id,user_id=users['reviewer'].id))
            lines=[f'Institution Name: {inst.name}',f'Institution Identifier: {"SYN-CONFLICT" if i==4 else inst.identifier}',f'Address: {inst.address}','Document Type: certificate','Issuing Authority: Synthetic Education Registry',f'Reference Number: CERT-{i:03}','Issue Date: 2025-01-01',f'Expiry Date: {"2025-12-31" if i==3 else "2027-12-31"}','Academic Year: 2026-2027','Programme: Synthetic Engineering','Intake: 60']
            cert=synthetic_pdf(lines)
            if i==6:
                # Rasterize into an image-only PDF: the pipeline must exercise Tesseract.
                with fitz.open(stream=cert,filetype='pdf') as doc:
                    pix=doc[0].get_pixmap(matrix=fitz.Matrix(2,2));scan=fitz.open();p=scan.new_page();p.insert_image(p.rect,stream=pix.tobytes('png'));cert=scan.tobytes();scan.close()
            photo=Image.new('RGB',(1000,650),'#eef2f6');draw=ImageDraw.Draw(photo);draw.rectangle((100,150,900,540),outline='#154e60',width=6);draw.text((70,50),'SYNTHETIC DEMONSTRATION FACILITY DIAGRAM',fill='black',font=ImageFont.load_default(size=24));draw.text((120,200),'Illustrative room; dimensions not asserted',fill='black',font=ImageFont.load_default(size=22));b=io.BytesIO();photo.save(b,format='PNG');infra=b.getvalue()
            files=[('infrastructure',infra,'facility.png','image/png')]
            if i!=2: files.append(('certificate',cert,'certificate.pdf','application/pdf'))
            if i==5: files.append(('other',infra,'copy.png','image/png'))
            for kind,data,filename,mime in files:
                d=Document(application_id=a.id,kind=kind);db.add(d);db.flush()
                v=DocumentVersion(document_id=d.id,version=1,filename=filename,storage_key=uid(),sha256=hashlib.sha256(data).hexdigest(),mime=mime,pages=1,uploaded_by=users['applicant'].id);storage.put(v.storage_key,data);db.add(v)
            db.flush();run,_=enqueue(db,users['applicant'],a,f'seed-{i}');run_ids.append(run.id)
            ground_truth.append({'application_id':a.id,'scenario':title,'expected':{1:'consistent',2:'missing-certificate',3:'expired',4:'identifier-conflict',5:'duplicate',6:'source-unavailable-and-OCR'}[i]})
        # Explicit demo seeding processes synchronously below; do not race the dispatcher.
        db.execute(delete(JobDispatch).where(JobDispatch.run_id.in_(run_ids)))
        db.commit()
    # Separate evaluation file; never imported by extraction or rules.
    Path('evaluation').mkdir(exist_ok=True);Path('evaluation/ground_truth.json').write_text(json.dumps(ground_truth,indent=2))
    for rid in run_ids: run_pipeline(rid)
    with SessionLocal() as db:
        # Seed real provider comparisons, not canned outcomes.
        from .main import verify
        from .schemas import VerificationIn
        reviewer=db.scalar(select(User).where(User.email=='reviewer@demo.local'))
        for v in db.scalars(select(DocumentVersion).join(Document).where(Document.kind=='certificate')):
            verify(v.id,VerificationIn(provider_id='synthetic-authority'),reviewer,db)
        # Publish demonstration results so applicant can inspect examples.
        for f in db.scalars(select(Finding)): f.released=True
        db.commit()
    print('Seeded six processed synthetic applications. Demo password: DemoOnly!2026')
if __name__=='__main__': seed()
