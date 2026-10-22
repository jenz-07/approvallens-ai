"""Explicit authorized-reference importer. JSON from a locally provided file; no URL fetching."""
import argparse,json
from pathlib import Path
from pydantic import BaseModel,Field,ConfigDict
from .db import SessionLocal
from .models import ReferenceSnapshot
class Record(BaseModel):
    model_config=ConfigDict(extra='forbid')
    institution_identifier:str=Field(min_length=1,max_length=100)
    institution_name:str=Field(min_length=1,max_length=200)
    intake:str=Field(pattern=r'^\d{1,6}$')
    unavailable:bool=False
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('file');parser.add_argument('--label',required=True);args=parser.parse_args()
    raw=json.loads(Path(args.file).read_text())
    if not isinstance(raw,dict) or len(raw)>10000:raise SystemExit('Provide a JSON object of up to 10,000 reference records')
    clean={str(k):Record.model_validate(v).model_dump(exclude_defaults=True) for k,v in raw.items()}
    if any(not k or len(k)>100 for k in clean):raise SystemExit('Reference keys must be 1–100 characters')
    with SessionLocal() as db:
        snap=ReferenceSnapshot(label=args.label[:150],records=clean);db.add(snap);db.commit();print(snap.id)
