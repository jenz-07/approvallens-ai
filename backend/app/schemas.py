from datetime import date
from typing import Literal
from pydantic import BaseModel,Field,ConfigDict
class Strict(BaseModel): model_config=ConfigDict(extra='forbid')
class Login(Strict):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1,max_length=200)
class ProgrammeIn(Strict):
    name: str = Field(min_length=1,max_length=200)
    intake: int = Field(ge=0,le=100000)
class ApplicationIn(Strict):
    institution_id: str
    title: str = Field(min_length=1,max_length=200)
    category: str = Field(min_length=1,max_length=100)
    reference_date: date
    programmes: list[ProgrammeIn] = Field(default_factory=list,max_length=100)
    declaration: dict = Field(default_factory=dict)
class Transition(Strict):
    status: Literal['Submitted','Under Review','Resubmitted','Preliminary Review Completed','Withdrawn']
    reason: str = Field(min_length=3,max_length=3000)
class CorrectionIn(Strict):
    name: str = Field(min_length=1,max_length=100)
    value: str = Field(max_length=1000)
    reason: str = Field(min_length=3,max_length=2000)
class ActionIn(Strict):
    status: Literal['Open','Acknowledged','Clarification Requested','Resolved','Dismissed with Reason']
    reason: str = Field(min_length=3,max_length=3000)
    release: bool = True
class ClarificationIn(Strict):
    finding_ids: list[str] = Field(default_factory=list,max_length=100)
    question: str = Field(min_length=3,max_length=3000)
class ReplyIn(Strict): text: str = Field(min_length=1,max_length=5000)
class VerificationIn(Strict):
    provider_id: Literal['synthetic-authority','manual']
    outcome: Literal['Verified','Mismatch Detected','Verification Pending','Source Unavailable','Manual Review Required','Not Supported'] = 'Manual Review Required'
    source: str = Field(default='',max_length=500)
    reference: str = Field(default='',max_length=500)
    observation: str = Field(default='',max_length=3000)
class InstitutionIn(Strict):
    name: str = Field(min_length=1,max_length=200)
    identifier: str = Field(min_length=1,max_length=100)
    address: str = Field(default='',max_length=2000)
class UserIn(Login):
    role: Literal['applicant','reviewer','administrator']
    institution_id: str | None = None
class AssignmentIn(Strict):
    application_id: str
    user_id: str
class NoteIn(Strict):
    action: Literal['Annotation','Additional Evidence Required','Inspection Recommended']
    reason: str = Field(min_length=3,max_length=3000)
class ChecklistIn(Strict):
    category: str = Field(min_length=1,max_length=100)
    kinds: list[Literal['certificate','infrastructure','floor_plan','photograph','other']] = Field(min_length=1,max_length=5)

from datetime import datetime
class UserOut(BaseModel):
    id:str
    created_at:datetime
    email:str
    role:Literal['applicant','reviewer','administrator']
    active:bool
class AuthOut(BaseModel):
    user:UserOut
    csrf:str
class ApplicationOut(BaseModel):
    id:str
    created_at:datetime
    institution_id:str
    title:str
    category:str
    reference_date:str
    status:str
    declaration:dict
class DocumentVersionOut(BaseModel):
    id:str
    created_at:datetime
    document_id:str
    version:int
    filename:str
    sha256:str
    mime:str
    pages:int
    uploaded_by:str
class RunOut(BaseModel):
    id:str
    created_at:datetime
    application_id:str
    rule_set_id:str
    snapshot_id:str
    input_snapshot:dict
    status:str
    stage:str
    error:str|None
    attempts:int
    heartbeat:datetime
    idempotency_key:str
