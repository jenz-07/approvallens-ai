# Product assessment and v3 release

## Winning potential

ApprovalLens AI has a credible competition demonstration when presented as an evidence-first preliminary-review workflow. It has a tangible user problem, actual document processing, a human decision boundary, and a complete correction loop. It is stronger as an accountable workflow product than as a claim of novel generative AI.

No competition rubric, competing entries or judging criteria were supplied, so a win probability or numerical score would be speculative.

| Criterion | Assessment | What would strengthen it further |
|---|---|---|
| Problem relevance | Strong, concrete review burden and missing-evidence use case | Interview authorized reviewers and document the actual workflow |
| Functional demonstration | Strong: actual PDF/OCR, findings, source preview, correction, revalidation and report | Present one short end-to-end scenario, not a feature tour |
| Differentiation | Moderate: extraction alone is common; linked provenance and revision history are the strongest story | Demonstrate saved reviewer effort with a baseline task |
| AI depth | Limited: native extraction, Tesseract OCR and deterministic parsing/rules; optional model interface has no implemented provider | Improve extraction across varied permissioned document layouts and measure it before adding models |
| Trust and boundaries | Strong prototype design: explicit simulated sources, unknowns, separate verification/expiry, human review | Independent security review and authorized domain validation |
| Evidence of impact | Preliminary: six synthetic scenarios do not establish real-world accuracy or productivity | Permissioned evaluation with unseen layouts and human-reviewed labels |
| Deployment maturity | Improved single-host configuration; target-host acceptance remains required | Run recovery/restore and production-concurrency exercises in the intended environment |

Google Document AI already documents extraction and classification capabilities: https://cloud.google.com/document-ai. Accordingly, the recommended pitch emphasizes traceable review and rectification, not OCR as unique technology. This is a product assessment, not proof that the workflow is exclusive or patentable.

## Implemented changes

- Revision Comparison workspace tab: compare a completed run with its preceding completed run; count improved, regressed and changed checks; disclose configuration changes and superseded document versions; open the stored evidence. Applicant visibility restrictions also apply to comparison data.
- Durable job outbox: persist delivery intent in the same transaction as each validation run, republish after broker interruptions, recover stale worker leases, and preserve idempotent processing. Migration supports pending v2 runs.
- Checklist enforcement: new required document types compile into a pinned immutable rule bundle. Changing an illustrative checklist no longer merely changes the upload instructions.
- Safer source interpretation: blank labels remain unknown; common field-label aliases are supported; conflicting repeated/page values remain ambiguous; coordinates are shown only for unique exact phrase matches.
- Workflow guards: block evidence/declaration edits during active processing, prevent stale historical retries and corrections to closed reviews, require fresh validation before review completion, and cap document versions per application.
- Correct severity pagination and dashboard paging. Administrator assignment selectors use actual application titles and reviewer accounts.
- Separate HTTPS production Compose stack, unique secret generator, clean first-admin bootstrap, schema-validated local reference import, readiness endpoint and backup/restore instructions.

## Four-minute demonstration

1. Sign in as the demo reviewer; open “Expired certificate.” Show the extracted expiry date beside its page evidence. Explain that severity is review priority, not a fraud probability.
2. Start review and request a replacement from the expiry finding. Sign in as applicant, reply, and replace the existing certificate with a current synthetic certificate. Resubmit.
3. Return as reviewer. Open Revision Comparison after processing completes: the expiry check improves, the earlier document is explicitly superseded, and the old finding is still inspectable. Highlight that the final decision stays human.
4. Show the unavailable-source example. It must stay unavailable, not magically verified. Complete a preliminary review with a reason and export its PDF report.

Use a separately seeded demo deployment; production intentionally does not contain known demo accounts. The deterministic demonstration reference date is 2026-07-01. Prepare a replacement with expiry after that reference date. Never substitute filenames for extraction evidence.

## Honest limits

The parser recognizes labelled fields rather than arbitrary tables/layouts. Six synthetic scenarios are not a real-world benchmark. Model-assisted extraction, cryptographic signature verification, forensic forgery detection, live portal integration and reliable photograph-based measurement are not implemented. Existing S3 support requires provider-specific acceptance. Do not claim regulatory certification or official AICTE rules. Measured reviewer-time reduction is a future validation goal, not an achieved result.
