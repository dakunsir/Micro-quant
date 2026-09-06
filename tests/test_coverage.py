from pathlib import Path

import pandas as pd

from microshare.coverage import (
    build_stock_history_coverage,
    validate_stock_history,
)
from microshare.storage import DailyPartitionStore, write_trade_cal


def _calendar(tmp_path: Path, dates: list[str]) -> None:
    write_trade_cal(
        tmp_path,
        "SSE",
        pd.DataFrame(
            {
                "exchange": ["SSE"] * len(dates),
                "cal_date": dates,
                "is_open": [True] * len(dates),
                "pretrade_date": dates,
            }
        ),
    )


def _write_history(tmp_path: Path, dates: list[str], *, skip: str | None = None) -> None:
    for date_value in dates:
        if date_value == skip:
            continue
        DailyPartitionStore(tmp_path / "stock" / "daily_kline").write(
            date_value,
            pd.DataFrame(
                {
                    "ts_code": ["000001.SZ"],
                    "trade_date": [date_value],
                    "open": [10.0], "high": [11.0], "low": [9.0],
                    "close": [10.5], "pre_close": [10.0],
                    "vol": [100.0], "amount": [1000.0],
                }
            ),
        )
        DailyPartitionStore(tmp_path / "stock" / "adj_factor").write(
            date_value,
            pd.DataFrame({
                "ts_code": ["000001.SZ"],
                "trade_date": [date_value],
                "adj_factor": [1.0],
            }),
        )
        DailyPartitionStore(tmp_path / "stock" / "daily_basic").write(
            date_value,
            pd.DataFrame({
                "ts_code": ["000001.SZ"],
                "trade_date": [date_value],
                "total_mv": [100.0],
            }),
        )
        for table, columns in {
            "stock_st": ["ts_code", "trade_date"],
            "suspend_d": ["ts_code", "trade_date"],
            "stk_limit": ["ts_code", "trade_date", "pre_close", "up_limit", "down_limit"],
        }.items():
            frame = pd.DataFrame(columns=columns)
            if table == "stk_limit":
                frame = pd.DataFrame({
                    "ts_code": ["000001.SZ"],
                    "trade_date": [date_value],
                    "pre_close": [10.0],
                    "up_limit": [11.0],
                    "down_limit": [9.0],
                })
            DailyPartitionStore(tmp_path / "stock" / table).write(
                date_value,
                frame,
            )


def test_coverage_reports_missing_physical_partitions(tmp_path):
    dates = ["20240102", "20240103", "20240104"]
    _calendar(tmp_path, dates)
    _write_history(tmp_path, dates, skip="20240103")

    report = build_stock_history_coverage(tmp_path, end_date="20240104")

    assert report["tables"]["daily_kline"]["missing_dates"] == ["20240103"]
    assert report["complete"] is False
    assert report["open_t1_ready_through"] is None


def test_coverage_accepts_empty_suspend_and_st_partitions(tmp_path):
    dates = ["20240102", "20240103", "20240104"]
    _calendar(tmp_path, dates)
    _write_history(tmp_path, dates)

    report = validate_stock_history(tmp_path, end_date="20240104")

    assert report["complete"] is True
    assert report["open_t1_ready_through"] == "20240103"
    assert report["tables"]["suspend_d"]["empty_partitions"] == 0


def test_validation_rejects_duplicate_keys_and_non_positive_adjustment(tmp_path):
    dates = ["20240102", "20240103"]
    _calendar(tmp_path, dates)
    _write_history(tmp_path, dates)
    DailyPartitionStore(tmp_path / "stock" / "daily_kline").write(
        "20240102",
        pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "000001.SZ"],
                "trade_date": ["20240102", "20240102"],
                "open": [10.0, 10.0], "high": [11.0, 11.0],
                "low": [9.0, 9.0], "close": [10.5, 10.5],
                "pre_close": [10.0, 10.0], "vol": [1.0, 1.0],
                "amount": [1.0, 1.0],
            }
        ),
    )
    DailyPartitionStore(tmp_path / "stock" / "adj_factor").write(
        "20240102",
        pd.DataFrame({
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240102"],
            "adj_factor": [0.0],
        }),
    )

    try:
        validate_stock_history(tmp_path, end_date="20240103")
    except RuntimeError as exc:
        assert "daily_kline" in str(exc)
        assert "adj_factor" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected invalid coverage to fail")
