import pandas as pd

from zer0share.quality.models import QualityFinding, Severity
from zer0share.quality.rules import (
    check_adjustment_factor_values,
    check_duplicate_key,
    check_market_data_values,
    check_required_columns,
)


def test_quality_finding_serializes_sample_as_json_text():
    finding = QualityFinding(
        table="daily_kline",
        date="20240102",
        severity=Severity.FAIL,
        rule="positive_prices",
        count=2,
        message="non-positive prices",
        sample=[{"ts_code": "000001.SZ", "close": 0}],
    )

    row = finding.to_row()

    assert row["table"] == "daily_kline"
    assert row["date"] == "20240102"
    assert row["severity"] == "fail"
    assert row["rule"] == "positive_prices"
    assert row["count"] == 2
    assert '"000001.SZ"' in row["sample"]


def test_check_required_columns_finds_missing_columns():
    df = pd.DataFrame({"ts_code": ["000001.SZ"]})

    findings = check_required_columns("daily_kline", "20240102", df, ["ts_code", "trade_date"])

    assert len(findings) == 1
    assert findings[0].severity == Severity.FAIL
    assert findings[0].rule == "required_columns"
    assert findings[0].count == 1
    assert "trade_date" in findings[0].message


def test_check_duplicate_key_finds_duplicate_rows():
    df = pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "trade_date": "20240102"},
            {"ts_code": "000001.SZ", "trade_date": "20240102"},
        ]
    )

    findings = check_duplicate_key("daily_kline", "20240102", df, ("ts_code", "trade_date"))

    assert len(findings) == 1
    assert findings[0].severity == Severity.FAIL
    assert findings[0].rule == "duplicate_key"
    assert findings[0].count == 2


def test_check_market_data_values_validates_prices_and_pct_chg():
    df = pd.DataFrame(
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": "20240102",
                "open": 0.0,
                "high": 9.5,
                "low": 9.0,
                "close": 10.0,
                "pre_close": 9.0,
                "pct_chg": 99.0,
                "vol": 0,
                "amount": 100.0,
            }
        ]
    )

    findings = check_market_data_values("daily_kline", "20240102", df)

    assert {finding.rule for finding in findings} == {
        "ohlc_relationship",
        "positive_prices",
        "positive_vol",
        "pct_chg_consistency",
    }
    assert {finding.severity for finding in findings} == {
        Severity.FAIL,
        Severity.WARN,
    }


def test_check_adjustment_factor_values_finds_non_positive_factor():
    df = pd.DataFrame(
        [
            {"ts_code": "000001.SZ", "trade_date": "20240102", "adj_factor": 0.0},
        ]
    )

    findings = check_adjustment_factor_values("adj_factor", "20240102", df)

    assert len(findings) == 1
    assert findings[0].severity == Severity.FAIL
    assert findings[0].rule == "positive_adj_factor"
