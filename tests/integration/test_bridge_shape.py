from ml.schemas import DocumentRecord
from ml.orchestration.pipeline import verify_submission

def rec(i, kind, fields, superseded=False):
    lines = [{"text": f'{k.replace("_", " ")}: {v}', "bbox": [1, 2, 3, 4], "conf": 88.0, "page": 1} for k, v in fields.items()]
    return DocumentRecord(i, kind, [{"page": 1, "text": "\n".join(l["text"] for l in lines), "lines": lines}], superseded=superseded)

def test_rows_shaped_like_backend_bridge_work_end_to_end():
    docs = [rec("v1", "identity_document", {"person_name": "Anita Raj Iyer", "date_of_birth": "2002-05-14", "national_id": "KA12345678"}),
            rec("v2", "application_form", {"person_name": "Anita Raj Iyer", "date_of_birth": "2002-05-14", "national_id": "KA12345678", "institution_id": "INST-1"}),
            rec("v3", "qualification_certificate", {"person_name": "Anita Raj Iyer", "date_of_birth": "2003-05-14", "qualification_year": "2024"})]
    r = verify_submission("app", docs)
    assert r["status"] == "complete" and any(f["unit"] == "person.date_of_birth" and f["status"] == "supported" for f in r["findings"])
    assert r["graph"]["stats"]["contradictions"] >= 1
