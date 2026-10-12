import datetime

from org_bloom.domain.dates import human_date, parse_date


def test_parse_date_from_org_forms():
    assert parse_date("<2026-10-01 Wed>") == datetime.date(2026, 10, 1)
    assert parse_date("[2026-10-01 Wed 10:00]") == datetime.date(2026, 10, 1)
    assert parse_date("2026-10-01") == datetime.date(2026, 10, 1)


def test_parse_date_rejects_garbage():
    assert parse_date("hier") is None
    assert parse_date("2026-13-45") is None


def test_human_date_by_language():
    date = datetime.date(2026, 10, 1)
    assert human_date(date, "fr") == "1 octobre 2026"
    assert human_date(date, "fr-FR", "10:00") == "1 octobre 2026 à 10:00"
    assert human_date(date, "en") == "October 1, 2026"
    assert human_date(date, "en", "10:00–11:00") == "October 1, 2026, 10:00–11:00"
    assert human_date(date, "de") == "2026-10-01"
