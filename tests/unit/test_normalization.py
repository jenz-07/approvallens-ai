from ml.extraction.normalization import *

def test_unambiguous_dates():
    assert parse_date("14/05/2002").iso == "2002-05-14" and not parse_date("14/05/2002").ambiguous
    assert parse_date("14 May 2002").iso == "2002-05-14"
    assert parse_date("May 14, 2002").iso == "2002-05-14"
    assert parse_date("2002-05-14").iso == "2002-05-14"

def test_ambiguous_date_keeps_both_readings():
    p = parse_date("03/04/2002")
    assert p.ambiguous and set(p.candidates) == {"2002-04-03", "2002-03-04"}
    assert compare_dates(p, parse_date("2002-03-04")) == "compatible_ambiguous"

def test_unparseable_and_impossible():
    assert not parse_date("14.V.2002").valid and not parse_date("31/02/2002").valid
    assert compare_dates(parse_date("x"), parse_date("2002-01-01")) == "unknown"

def test_ocr_fold_detects_confusables_not_real_changes():
    assert ocr_fold("AB1O5") == ocr_fold("AB1O5".replace("O", "0"))
    assert ocr_fold("KA48201937") != ocr_fold("KA48201973")

def test_name_variants_vs_different_people():
    assert name_similarity("Mohammed Rafi Khan", "Muhammad Rafi Khan") > 0.9
    assert name_similarity("Rajesh Kumar Singh", "Rajesh K. Singh") > 0.86
    assert name_similarity("Deepa Prasad Patel", "Karthik Prasad Das") < 0.7

def test_address_numbers_matter():
    assert address_similarity("12 MG Road, Pune", "12 MG Rd Pune") > 0.8
    assert address_similarity("12 MG Road, Pune", "14 MG Road, Pune") < 0.8
