from app.cleaning import canonical_province, clean_rows, clean_town


def test_province_aliases():
    assert canonical_province("wc") == "Western Cape"
    assert canonical_province(" W Cape ") == "Western Cape"
    assert canonical_province("Gauteng Province") == "Gauteng"
    assert canonical_province("Kwazulu Natal") == "KwaZulu-Natal"
    assert canonical_province("North-West") == "North West"
    assert canonical_province("Narnia") is None
    assert canonical_province("") is None


def test_clean_town_casing_and_whitespace():
    assert clean_town("  cape   town ") == "Cape Town"
    assert clean_town("GRAAFF-REINET") == "Graaff-Reinet"


def test_duplicates_collapse_across_spellings():
    rows = [
        {"town": "Cape Town", "province": "Western Cape"},
        {"town": " cape town ", "province": "wc"},
    ]
    result = clean_rows(rows)
    assert len(result.places) == 1
    assert result.duplicates == 1


def test_same_town_different_province_is_kept():
    rows = [
        {"town": "Ladysmith", "province": "Western Cape"},
        {"town": "Ladysmith", "province": "KZN"},
    ]
    assert len(clean_rows(rows).places) == 2


def test_bad_rows_are_rejected_with_reasons():
    rows = [
        {"town": "", "province": "Gauteng"},
        {"town": "Atlantis", "province": ""},
        {"town": "Springbok", "province": "Narnia"},
        {"town": "12345", "province": "Gauteng"},
    ]
    result = clean_rows(rows)
    assert result.places == []
    assert [r.reason for r in result.rejected] == [
        "missing town", "missing province", "unknown province", "town contains digits",
    ]
