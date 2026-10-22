"""Versioned document requirements: which fields each document kind is expected to carry."""
RULESET_VERSION = "requirements/1"
EXPECTED_FIELDS = {
    "identity_document": ["person_name", "date_of_birth", "national_id"],
    "application_form": ["person_name", "date_of_birth", "national_id", "institution_name", "institution_id", "address"],
    "certificate": ["institution_name", "institution_id", "reference_number", "issue_date", "expiry_date", "address"],
    "qualification_certificate": ["person_name", "qualification_year"],
    "guarantor_declaration": ["person_name", "date_of_birth", "national_id"],
}
