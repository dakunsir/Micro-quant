from datetime import date
import pytest
from zer0share.dateutil import add_days, date_str, month_ranges, parse_date, today, week_ranges


def test_today_returns_yyyymmdd_string():
    result = today()
    assert len(result) == 8
    assert result.isdigit()


def test_add_days_simple():
    assert add_days("20240101", 1) == "20240102"


def test_add_days_year_boundary():
    assert add_days("20161231", 1) == "20170101"


def test_add_days_leap_year():
    assert add_days("20240229", 1) == "20240301"


def test_add_days_negative():
    assert add_days("20240103", -1) == "20240102"


def test_month_ranges_single_month():
    assert month_ranges("20240115", "20240125") == [("20240115", "20240125")]


def test_month_ranges_two_months():
    assert month_ranges("20240115", "20240210") == [
        ("20240115", "20240131"),
        ("20240201", "20240210"),
    ]


def test_month_ranges_three_months():
    assert month_ranges("20240115", "20240301") == [
        ("20240115", "20240131"),
        ("20240201", "20240229"),
        ("20240301", "20240301"),
    ]


def test_month_ranges_year_boundary():
    assert month_ranges("20231201", "20240131") == [
        ("20231201", "20231231"),
        ("20240101", "20240131"),
    ]


def test_week_ranges_single_week():
    result = week_ranges("20240104", "20240105")
    assert len(result) == 1
    week_num, monday = result[0]
    assert week_num == "202401"
    assert monday == "20240101"


def test_week_ranges_two_weeks():
    result = week_ranges("20240104", "20240112")
    assert len(result) == 2
    assert result[0][0] == "202401"
    assert result[1][0] == "202402"


def test_week_ranges_advances_by_7():
    result = week_ranges("20240101", "20240107")
    assert len(result) == 1


def test_date_str_with_string():
    assert date_str("20240102") == "20240102"


def test_date_str_with_date_object():
    assert date_str(date(2024, 1, 2)) == "20240102"


def test_parse_date_valid():
    assert parse_date("20240102") == date(2024, 1, 2)


def test_parse_date_invalid_raises():
    with pytest.raises(ValueError):
        parse_date("2024-01-02")
