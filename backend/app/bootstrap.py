"""Operator-only clean production bootstrap. No demo users or synthetic registry."""
from getpass import getpass
from sqlalchemy import select
from .db import SessionLocal
from .models import User,ReferenceSnapshot,ProviderConfig,RuleSet,RuleVersion,ChecklistTemplate,ChecklistItem
from .security import hasher
from .rules import RuleDefinition

def bootstrap():
    with SessionLocal() as db:
        if db.scalar(select(User.id)):
            raise SystemExit('Users already exist. Use the existing administrator; bootstrap does not overwrite accounts.')
        email=input('Administrator email: ').strip().lower()
        password=getpass('Administrator password (12+ characters): ')
        confirm=getpass('Repeat password: ')
        if '@' not in email or len(password)<12 or password!=confirm:raise SystemExit('Invalid email, short password or password mismatch')
        db.add(User(email=email,role='administrator',password_hash=hasher.hash(password)))
        # Empty reference data never reports synthetic success on real submissions.
        db.add(ReferenceSnapshot(label='Empty operator reference snapshot',records={}))
        db.add(ProviderConfig(provider_id='synthetic-authority',available=False))
        if not db.scalar(select(RuleSet.id)):
            rs=RuleSet(name='Illustrative evidence checklist',version=1,active=True);db.add(rs);db.flush()
            for kind in ('certificate','infrastructure'):
                r=RuleDefinition(rule_id='required-'+kind,version=1,title='Evidence required: '+kind,description='Illustrative presence requirement',required_document=kind,check_type='required_document',explanation='Presence only; not an official regulatory requirement.')
                db.add(RuleVersion(rule_set_id=rs.id,rule_id=r.rule_id,version=1,definition=r.model_dump(mode='json')))
        for category in ('Extension of Approval','Change in Intake'):
            c=ChecklistTemplate(category=category,version=1,active=True);db.add(c);db.flush()
            for kind in ('certificate','infrastructure'):db.add(ChecklistItem(template_id=c.id,kind=kind,description='Illustrative evidence requirement'))
        db.commit()
    print('Administrator created. Sign in, create institutions/users, and review the illustrative configuration.')
if __name__=='__main__':bootstrap()
