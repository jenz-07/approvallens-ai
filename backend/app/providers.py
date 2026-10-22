from typing import Protocol
from datetime import datetime, timezone
class AIProvider(Protocol):
    """Implement server-side only; validate extracted facts against page evidence.
    Document text is data, never instructions. No tools or network actions from text.
    A future implementation must be explicitly enabled and disclose external processing.
    """
    def extract(self, pages: list[dict]) -> list[dict]: ...
class VerificationProvider(Protocol):
    provider_id: str
    supported_types: list[str]
    def verify(self, fields: dict, records: dict, available: bool) -> dict: ...
class SimulatedAuthority:
    provider_id='synthetic-authority'
    supported_types=['certificate']
    def verify(self, fields, records, available=True):
        base={'provider_name':'Synthetic issuing authority','mode':'simulated','method':'Reference lookup and field comparison','request_timestamp':datetime.now(timezone.utc).isoformat(),'source_reference':'Separate synthetic registry','disclosure':'Simulated issuing-authority response — demonstration only.','matched_fields':[],'mismatched_fields':[]}
        record=records.get(fields.get('reference_number',''))
        if not available or (record and record.get('unavailable')): return dict(base,outcome='Source Unavailable',reason='Synthetic source configured unavailable')
        if not record: return dict(base,outcome='Verification Pending',reason='Unknown reference; consult an authorized source manually')
        for k,v in record.items():
            if k=='unavailable': continue
            if k not in fields: continue
            base['matched_fields' if str(fields[k])==str(v) else 'mismatched_fields'].append(k)
        if base['mismatched_fields']: outcome='Mismatch Detected'
        elif not fields.get('institution_identifier'): outcome='Manual Review Required'
        else: outcome='Verified'
        return dict(base,outcome=outcome,reason='Only compared fields are covered; validity is assessed separately')
