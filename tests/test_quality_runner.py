from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from micro.quality.models import QualityRunOptions
from micro.quality.runner import QualityRunner


def _write_parquet(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(pd.DataFrame(rows), preserve_index=False), path)


def _write_trade_cal(data_dir: Path, dates: list[str]) -> None:
    _write_parquet(
        data_dir / "stock" / "trade_cal" / "exchange=SSE" / "data.parquet",
        [
            {
                "exchange": "SSE",
                "cal_date": date,
                "is_open": True,
                "pretrade_date": date,
            }
            for date in dates
        ],
    )


def test_runner_ignores_futures_only_trading_days_for_stock_targets(tmp_path):
    _write_parquet(
        tmp_path / "stock" / "trade_cal" / "exchange=SSE" / "data.parquet",
        [
            {
                "exchange": "SSE",
                "cal_date": "20240102",
                "is_open": False,
                "pretrade_date": "20231229",
            }
        ],
    )
    _write_parquet(
        tmp_path / "stock" / "trade_cal" / "exchange=SHFE" / "data.parquet",
        [
            {
                "exchange": "SHFE",
                "cal_date": "20240102",
                "is_open": True,
                "pretrade_date": "20231229",
            }
        ],
    )
    (tmp_path / "stock" / "daily_kline").mkdir(parents=True)
    runner = QualityRunner(tmp_path)

    report = runner.run(
        QualityRunOptions(
            mode="full",
            tables=("daily_kline",),
            start_date="20240102",
            end_date="20240102",
        )
    )

    assert report.findings == []
    assert report.summaries[0].partitions == 0


def test_runner_reports_missing_partition_from_trade_calendar(tmp_path):
    _write_trade_cal(tmp_path, ["20240102"])
    (tmp_path / "stock" / "daily_kline").mkdir(parents=True)
    runner = QualityRunner(tmp_path)

    report = runner.run(
        QualityRunOptions(
            mode="full",
            tables=("daily_kline",),
            start_date="20240102",
            end_date="20240102",
        )
    )

    assert report.fail_count == 0
    assert report.warn_count == 1
    assert report.findings[0].rule == "missing_partition"
    assert report.findings[0].date == "20240102"


def test_runner_passes_valid_daily_kline_partition(tmp_path):
    _write_trade_cal(tmp_path, ["20240102"])
    _write_parquet(
        tmp_path / "stock" / "daily_kline" / "date=20240102" / "data.parquet",
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": "20240102",
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "pre_close": 10.0,
                "change": 0.5,
                "pct_chg": 5.0,
                "vol": 100.0,
                "amount": 1000.0,
            }
        ],
    )
    runner = QualityRunner(tmp_path)

    report = runner.run(
        QualityRunOptions(
            mode="full",
            tables=("daily_kline",),
            start_date="20240102",
            end_date="20240102",
        )
    )

    assert report.fail_count == 0
    assert report.warn_count == 0
    assert report.summaries[0].rows == 1
    assert report.summaries[0].partitions == 1


def test_runner_warns_when_adjustment_coverage_is_low(tmp_path):
    _write_trade_cal(tmp_path, ["20240102"])
    _write_parquet(
        tmp_path / "stock" / "adj_factor" / "date=20240102" / "data.parquet",
        [
            {"ts_code": "000001.SZ", "trade_date": "20240102", "adj_factor": 1.0},
            {"ts_code": "000002.SZ", "trade_date": "20240102", "adj_factor": 1.0},
        ],
    )
    _write_parquet(
        tmp_path / "stock" / "daily_kline" / "date=20240102" / "data.parquet",
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": "20240102",
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "pre_close": 10.0,
                "change": 0.5,
                "pct_chg": 5.0,
                "vol": 100.0,
                "amount": 1000.0,
            },
            {
                "ts_code": "000003.SZ",
                "trade_date": "20240102",
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "pre_close": 10.0,
                "change": 0.5,
                "pct_chg": 5.0,
                "vol": 100.0,
                "amount": 1000.0,
            }
        ],
    )
    runner = QualityRunner(tmp_path)

    report = runner.run(
        QualityRunOptions(
            mode="full",
            tables=("adj_factor",),
            start_date="20240102",
            end_date="20240102",
        )
    )

    assert report.fail_count == 0
    assert report.warn_count == 1
    assert report.findings[0].rule == "adjustment_market_coverage"
    assert report.findings[0].severity.value == "warn"


def test_runner_does_not_warn_when_adjustment_has_extra_codes(tmp_path):
    _write_trade_cal(tmp_path, ["20240102"])
    _write_parquet(
        tmp_path / "stock" / "adj_factor" / "date=20240102" / "data.parquet",
        [
            {"ts_code": "000001.SZ", "trade_date": "20240102", "adj_factor": 1.0},
            {"ts_code": "000002.SZ", "trade_date": "20240102", "adj_factor": 1.0},
        ],
    )
    _write_parquet(
        tmp_path / "stock" / "daily_kline" / "date=20240102" / "data.parquet",
        [
            {
                "ts_code": "000001.SZ",
                "trade_date": "20240102",
                "open": 10.0,
                "high": 11.0,
                "low": 9.0,
                "close": 10.5,
                "pre_close": 10.0,
                "change": 0.5,
                "pct_chg": 5.0,
                "vol": 100.0,
                "amount": 1000.0,
            }
        ],
    )
    runner = QualityRunner(tmp_path)

    report = runner.run(
        QualityRunOptions(
            mode="full",
            tables=("adj_factor",),
            start_date="20240102",
            end_date="20240102",
        )
    )

    assert not [
        finding for finding in report.findings
        if finding.rule == "adjustment_market_coverage"
    ]


def test_runner_warns_when_stock_adjusted_return_jumps(tmp_path):
    _write_trade_cal(tmp_path, ["20240102", "20240103"])
    for date, close in [("20240102", 10.0), ("20240103", 15.0)]:
        _write_parquet(
            tmp_path / "stock" / "daily_kline" / f"date={date}" / "data.parquet",
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": date,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "pre_close": close,
                    "change": 0.0,
                    "pct_chg": 0.0,
                    "vol": 100.0,
                    "amount": 1000.0,
                }
            ],
        )
        _write_parquet(
            tmp_path / "stock" / "adj_factor" / f"date={date}" / "data.parquet",
            [{"ts_code": "000001.SZ", "trade_date": date, "adj_factor": 1.0}],
        )
    runner = QualityRunner(tmp_path)

    report = runner.run(
        QualityRunOptions(
            mode="full",
            tables=("adj_factor",),
            start_date="20240102",
            end_date="20240103",
        )
    )

    jump_findings = [finding for finding in report.findings if finding.rule == "adjusted_return_jump"]
    assert len(jump_findings) == 1
    assert jump_findings[0].severity.value == "warn"
    assert jump_findings[0].date == "20240103"
    assert jump_findings[0].sample[0]["adjusted_return"] == 0.5


def test_runner_uses_adjusted_close_for_return_jump_detection(tmp_path):
    _write_trade_cal(tmp_path, ["20240102", "20240103"])
    for date, close, adj_factor in [
        ("20240102", 10.0, 1.0),
        ("20240103", 5.0, 2.0),
    ]:
        _write_parquet(
            tmp_path / "stock" / "daily_kline" / f"date={date}" / "data.parquet",
            [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": date,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "pre_close": close,
                    "change": 0.0,
                    "pct_chg": 0.0,
                    "vol": 100.0,
                    "amount": 1000.0,
                }
            ],
        )
        _write_parquet(
            tmp_path / "stock" / "adj_factor" / f"date={date}" / "data.parquet",
            [{"ts_code": "000001.SZ", "trade_date": date, "adj_factor": adj_factor}],
        )
    runner = QualityRunner(tmp_path)

    report = runner.run(
        QualityRunOptions(
            mode="full",
            tables=("adj_factor",),
            start_date="20240102",
            end_date="20240103",
        )
    )

    assert not [
        finding for finding in report.findings
        if finding.rule == "adjusted_return_jump"
    ]


def test_runner_ignores_bj_codes_for_adjusted_return_jump_detection(tmp_path):
    _write_trade_cal(tmp_path, ["20240102", "20240103"])
    for date, close in [("20240102", 10.0), ("20240103", 20.0)]:
        _write_parquet(
            tmp_path / "stock" / "daily_kline" / f"date={date}" / "data.parquet",
            [
                {
                    "ts_code": "920001.BJ",
                    "trade_date": date,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "pre_close": close,
                    "change": 0.0,
                    "pct_chg": 0.0,
                    "vol": 100.0,
                    "amount": 1000.0,
                }
            ],
        )
        _write_parquet(
            tmp_path / "stock" / "adj_factor" / f"date={date}" / "data.parquet",
            [{"ts_code": "920001.BJ", "trade_date": date, "adj_factor": 1.0}],
        )
    runner = QualityRunner(tmp_path)

    report = runner.run(
        QualityRunOptions(
            mode="full",
            tables=("adj_factor",),
            start_date="20240102",
            end_date="20240103",
        )
    )

    assert not [
        finding for finding in report.findings
        if finding.rule == "adjusted_return_jump"
    ]
