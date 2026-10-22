#!/usr/bin/env python3
"""Create fictional cross-document demo PDFs (the spec's DOB example) in sample-documents/xdoc/."""
from pathlib import Path
from reportlab.pdfgen import canvas
OUT = Path(__file__).resolve().parents[1] / "sample-documents" / "xdoc"; OUT.mkdir(parents=True, exist_ok=True)
DOCS = {
 "1-identity_document.pdf": ["IDENTITY DOCUMENT (FICTIONAL)", "Person Name: Anita Raj Iyer", "Date of Birth: 2002-05-14", "National ID: KA48201937"],
 "2-application_form.pdf": ["APPLICATION FORM (FICTIONAL)", "Person Name: Anita Raj Iyer", "Date of Birth: 2002-05-14", "National ID: KA48201937", "Institution Name: Sunrise College of Engineering", "Institution ID: INST-48213", "Address: 12 MG Road, Coimbatore"],
 "3-qualification_certificate-DOB-MISMATCH.pdf": ["QUALIFICATION CERTIFICATE (FICTIONAL)", "Person Name: Anita Raj Iyer", "Date of Birth: 2003-05-14", "Qualification Year: 2024"],
 "3b-qualification_certificate-CORRECTED.pdf": ["QUALIFICATION CERTIFICATE (FICTIONAL)", "Person Name: Anita Raj Iyer", "Date of Birth: 2002-05-14", "Qualification Year: 2024"],
}
for name, lines in DOCS.items():
    c = canvas.Canvas(str(OUT / name)); c.setFont("Helvetica", 14)
    for i, t in enumerate(lines): c.drawString(60, 780 - 32 * i, t)
    c.save()
(OUT / "README.txt").write_text("Upload 1, 2 and 3 with categories identity_document, application_form, qualification_certificate, run validation, then open the 'Evidence Graph' tab.\nUpload 3b as a replacement version of the qualification certificate to see supersession.\nAll people and institutions are fictional.\n")
print("wrote", len(DOCS), "pdfs")
