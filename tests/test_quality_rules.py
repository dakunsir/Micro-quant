from zer0share.quality.models import QualityFinding, Severity


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
