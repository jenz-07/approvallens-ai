"""Build evidence analysis from the SAME immutable snapshot used by validation.
Raw page text is retained. Corrections are explicitly tagged; they are not OCR facts.
No trained model or synthetic calibration is enabled in the production pipeline.
"""
from sqlalchemy import select
from .models import DocumentVersion,PageText,ExtractedField
from .extraction import ALIASES,FIELDS
from ml.schemas import DocumentRecord
from ml.orchestration.pipeline import verify_submission

def analyze_run(db,run):
    docs=[]
    for vid in run.input_snapshot['version_ids']:
        v=db.get(DocumentVersion,vid)
        fields=list(db.scalars(select(ExtractedField).where(ExtractedField.version_id==vid)))
        corrections=list({c['name']:c for c in run.input_snapshot.get('corrections',[]) if c['version_id']==vid}.values())
        pages=[]
        for p in db.scalars(select(PageText).where(PageText.version_id==vid).order_by(PageText.page)):
            lines=[]
            for text in p.text.splitlines():
                label=text.split(':',1)[0].strip().casefold()
                overridden=any(label in [x.casefold() for x in ALIASES.get(c['name'],[FIELDS.get(c['name'],c['name'].replace('_',' '))])] for c in corrections)
                if overridden:continue
                matching=[f for f in fields if f.page==p.page and f.excerpt==text.strip()]
                f=matching[0] if len(matching)==1 else None
                lines.append({'text':text,'bbox':f.bbox if f else None,'conf':f.ocr_confidence if f else None})
            pages.append({'page':p.page,'text':p.text,'lines':lines})
        if not pages:pages=[{'page':1,'text':'','lines':[]}]
        for c in corrections:
            original=next((f for f in fields if f.name==c['name']),None)
            page=next((p for p in pages if p['page']==(original.page if original else 1)),pages[0])
            page['lines'].append({'text':FIELDS.get(c['name'],c['name'].replace('_',' '))+': '+c['value'],'bbox':None,'conf':None})
        docs.append(DocumentRecord(document_id=vid,kind=run.input_snapshot['document_kinds'][vid],version=v.version,pages=pages,metadata={'filename':v.filename,'corrections':corrections}))
    result=verify_submission(run.application_id,docs)
    result['calibration_note']='Deterministic evidence analysis. No calibrated probability is available. Synthetic calibration is offline research only.'
    result['run_id']=run.id
    result['input_version_ids']=list(run.input_snapshot['version_ids'])
    result['corrections']=run.input_snapshot.get('corrections',[])
    result['disclaimer']='A contradiction requires review; it is not proof of fraud. Missing-field rules are illustrative research assumptions.'
    return result
