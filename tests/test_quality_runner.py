from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from zer0share.quality.models import QualityRunOptions
from zer0share.quality.runner import QualityRunner


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
