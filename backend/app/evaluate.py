"""Evaluate seeded synthetic scenarios against ground truth.

Run after `python -m app.seed` and before editing scenarios:
    python -m app.evaluate [--labels evaluation/ground_truth.json]

Ground truth lives only here and in the evaluation file; the extraction, rules and worker
modules never import it. Results cover a tiny synthetic set and the SIMULATED provider only;
they are not real-world accuracy or live-verification performance.
"""
import argparse, json
from pathlib import Path
from sqlalchemy import select
from .db import SessionLocal
from .models import Application, ValidationRun, Finding, ExtractedField, DocumentVersion, Document, VerificationAttempt

NON_PASS = {'Failed', 'Review Needed'}
# Rules expected to be flagged per scenario label. Scenario 4's registry record is keyed to the
# genuine identifier, so the reference rule is also expected to flag it (documented dependency).
EXPECTED_FLAGS = {'consistent': set(), 'missing-certificate': {'required-certificate'}, 'expired': {'expiry'},
                  'identifier-conflict': {'identifier', 'reference'}, 'duplicate': {'duplicate'}, 'source-unavailable-and-OCR': set()}
EXPECTED_VERIFICATION = {'consistent': 'Verified', 'expired': 'Verified', 'identifier-conflict': 'Mismatch Detected',
                         'duplicate': 'Verified', 'source-unavailable-and-OCR': 'Source Unavailable'}

def expected_fields(index, label):
    """Synthetic certificate values written by the seed for scenario `index` (1-based)."""
    return {'institution_name': 'Synthetic Institute of Technology',
            'institution_identifier': 'SYN-CONFLICT' if label == 'identifier-conflict' else 'SYN-001',
            'reference_number': f'CERT-{index:03}', 'issue_date': '2025-01-01',
            'expiry_date': '2025-12-31' if label == 'expired' else '2027-12-31', 'intake': '60'}

def main():
    p = argparse.ArgumentParser(); p.add_argument('--labels', default='evaluation/ground_truth.json'); args = p.parse_args()
    labels = json.loads(Path(args.labels).read_text())
    tp = fp = fn = fc = ft = 0; scenarios = []; seconds = []; verification = []
    with SessionLocal() as db:
        for index, item in enumerate(labels, 1):
            label = item['expected']; app = db.get(Application, item['application_id'])
            run = db.scalars(select(ValidationRun).where(ValidationRun.application_id == app.id).order_by(ValidationRun.created_at)).first()
            if run is None or run.status != 'Completed':
                raise SystemExit(f'Run for "{app.title}" is not Completed; wait for processing, then re-run.')
            seconds.append((run.heartbeat - run.created_at).total_seconds())
            flagged = {f.rule_id for f in db.scalars(select(Finding).where(Finding.run_id == run.id)) if f.result in NON_PASS}
            want = EXPECTED_FLAGS[label]
            tp += len(flagged & want); fp += len(flagged - want); fn += len(want - flagged)
            scenarios.append({'scenario': item['scenario'], 'expected': sorted(want), 'detected': sorted(flagged), 'correct': flagged == want})
            versions = db.scalars(select(DocumentVersion).join(Document, Document.id == DocumentVersion.document_id).where(Document.application_id == app.id, Document.kind == 'certificate')).all()
            if versions:
                got = {f.name: f.value for f in db.scalars(select(ExtractedField).where(ExtractedField.version_id == versions[0].id))}
                for k, v in expected_fields(index, label).items():
                    ft += 1; fc += int(got.get(k) == v)
            if label in EXPECTED_VERIFICATION:
                att = db.scalars(select(VerificationAttempt).where(VerificationAttempt.application_id == app.id, VerificationAttempt.provider_id == 'synthetic-authority').order_by(VerificationAttempt.created_at.desc())).first()
                verification.append({'scenario': item['scenario'], 'expected': EXPECTED_VERIFICATION[label], 'observed': att.outcome if att else None, 'mode': 'simulated'})
    result = {'dataset_applications': len(labels), 'finding_true_positives': tp, 'finding_false_positives': fp, 'finding_false_negatives': fn,
              'finding_precision': round(tp / (tp + fp), 3) if tp + fp else None, 'finding_recall': round(tp / (tp + fn), 3) if tp + fn else None,
              'field_exact_match': {'correct': fc, 'total': ft, 'accuracy': round(fc / ft, 3) if ft else None},
              'mean_processing_seconds': round(sum(seconds) / len(seconds), 3), 'scenarios': scenarios, 'simulated_verification': verification,
              'limitations': 'Tiny synthetic set; exact string match; flagged = Failed or Review Needed. Simulated provider only; not real-world or live-verification performance.'}
    print(json.dumps(result, indent=2))

if __name__ == '__main__': main()
