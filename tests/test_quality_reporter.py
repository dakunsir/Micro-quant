import json

from zer0share.quality.models import (
    QualityFinding,
    QualityRunOptions,
    QualityRunReport,
    Severity,
    TableSummary,
)
from zer0share.quality.reporter import QualityReporter, format_summary


def test_reporter_writes_summary_findings_and_metadata(tmp_path):
    report = QualityRunReport(
        options=QualityRunOptions(mode="daily", tables=("daily_kline",), date="20240102"),
        summaries=[TableSummary("daily_kline", "stock", 1, 1, 0, 0, 1)],
        findings=[
            QualityFinding("daily_kline", "20240102", Severity.FAIL, "positive_prices", 1, "bad price")
        ],
    )
    reporter = QualityReporter(tmp_path)

    output_dir = reporter.write(report)

    assert (output_dir / "summary.csv").exists()
    assert (output_dir / "findings.csv").exists()
    metadata = json.loads((output_dir / "metadata.json").read_text())
    assert metadata["mode"] == "daily"
    assert metadata["tables"] == ["daily_kline"]
    assert metadata["date"] == "20240102"
    assert metadata["created_at"]
    assert "git_commit" in metadata


def test_format_summary_includes_table_counts():
    report = QualityRunReport(
        options=QualityRunOptions(mode="daily", tables=("daily_kline",), date="20240102"),
        summaries=[TableSummary("daily_kline", "stock", 1, 1, 1, 0, 0)],
        findings=[],
    )

    text = format_summary(report)

    assert "daily_kline" in text
    assert "partitions" in text
    assert "rows" in text
