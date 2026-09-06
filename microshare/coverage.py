"""Coverage and readiness checks for stock history data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq


STOCK_HISTORY_START_DATES = {
    "daily_kline": "20150101",
    "adj_factor": "20150101",
    "daily_basic": "20151231",
    "stock_st": "20151231",
    "suspend_d": "20150101",
    "stk_limit": "20150101",
}

_REQUIRED_COLUMNS = {
    "daily_kline": {
        "ts_code", "trade_date", "open", "high", "low", "close",
        "pre_close", "vol", "amount",
    },
    "adj_factor": {"ts_code", "trade_date", "adj_factor"},
    "daily_basic": {"ts_code", "trade_date", "total_mv"},
    "stock_st": {"ts_code", "trade_date"},
    "suspend_d": {"ts_code", "trade_date"},
    "stk_limit": {"ts_code", "trade_date", "pre_close", "up_limit", "down_limit"},
}
_ALLOW_EMPTY = {"stock_st", "suspend_d"}
_KEY_COLUMNS = ("trade_date", "ts_code")


def _normalize_dates(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values.astype(str), errors="coerce").dt.strftime("%Y%m%d")


def _calendar_dates(data_dir: Path, start_date: str, end_date: str) -> list[str]:
    path = data_dir / "stock" / "trade_cal" / "exchange=SSE" / "data.parquet"
    if not path.exists():
        raise FileNotFoundError("SSE trade calendar is not synchronized")
    frame = pd.read_parquet(path, columns=["cal_date", "is_open"])
    dates = _normalize_dates(frame.loc[frame["is_open"].fillna(False).astype(bool), "cal_date"])
    return sorted(d for d in dates.dropna().unique().tolist() if start_date <= d <= end_date)


def _partition_path(data_dir: Path, table: str, date_value: str) -> Path:
    return data_dir / "stock" / table / f"date={date_value}" / "data.parquet"


def _partition_dates(data_dir: Path, table: str) -> set[str]:
    table_dir = data_dir / "stock" / table
    return {
        path.parent.name.removeprefix("date=")
        for path in table_dir.glob("date=*/data.parquet")
    }


def _inspect_partition(path: Path, table: str, date_value: str) -> list[str]:
    errors: list[str] = []
    try:
        parquet_file = pq.ParquetFile(path)
        columns = set(parquet_file.schema_arrow.names)
        missing_columns = sorted(_REQUIRED_COLUMNS[table] - columns)
        if missing_columns:
            errors.append(f"missing columns: {','.join(missing_columns)}")
        if parquet_file.metadata is not None and parquet_file.metadata.num_rows == 0:
            if table not in _ALLOW_EMPTY:
                errors.append("empty partition")
            return errors

        frame = pd.read_parquet(path)
        if "trade_date" in frame.columns:
            dates = set(_normalize_dates(frame["trade_date"].dropna()).dropna())
            if dates and dates != {date_value}:
                errors.append(f"partition trade_date mismatch: {sorted(dates)[:3]}")
        if set(_KEY_COLUMNS).issubset(frame.columns):
            duplicates = int(frame.duplicated(list(_KEY_COLUMNS)).sum())
            if duplicates:
                errors.append(f"duplicate keys: {duplicates}")
        if table == "adj_factor" and "adj_factor" in frame.columns:
            invalid = int((pd.to_numeric(frame["adj_factor"], errors="coerce") <= 0).sum())
            if invalid:
                errors.append(f"non-positive adj_factor: {invalid}")
    except Exception as exc:
        errors.append(f"unreadable parquet: {exc}")
    return errors


def _continuous_prefix(
    dates: list[str],
    available: dict[str, bool],
) -> str | None:
    if not dates:
        return None
    last_complete_index = -1
    for index, date_value in enumerate(dates):
        if not available.get(date_value, False):
            break
        last_complete_index = index
    if last_complete_index < 1:
        return None
    return dates[last_complete_index - 1]


def build_stock_history_coverage(
    data_dir: Path,
    *,
    start_date: str = "20150101",
    end_date: str,
    validate_partitions: bool = False,
) -> dict[str, Any]:
    """Return physical partition coverage and T+1 readiness for stock history."""
    data_dir = Path(data_dir)
    calendar_dates = _calendar_dates(data_dir, start_date, end_date)
    tables: dict[str, dict[str, Any]] = {}
    complete_for_open_t1: dict[str, bool] = {date_value: True for date_value in calendar_dates}

    for table, table_start in STOCK_HISTORY_START_DATES.items():
        expected = [date_value for date_value in calendar_dates if date_value >= table_start]
        actual = _partition_dates(data_dir, table)
        missing = [date_value for date_value in expected if date_value not in actual]
        invalid: dict[str, list[str]] = {}
        empty: list[str] = []
        for date_value in expected:
            path = _partition_path(data_dir, table, date_value)
            if not path.exists():
                continue
            try:
                metadata = pq.ParquetFile(path).metadata
                if metadata is not None and metadata.num_rows == 0 and table not in _ALLOW_EMPTY:
                    empty.append(date_value)
            except Exception as exc:
                invalid[date_value] = [f"unreadable parquet: {exc}"]
        if validate_partitions:
            for date_value in expected:
                path = _partition_path(data_dir, table, date_value)
                if path.exists():
                    errors = _inspect_partition(path, table, date_value)
                    if errors:
                        invalid[date_value] = errors
                else:
                    invalid[date_value] = ["missing partition"]

        covered = [date_value for date_value in expected if date_value in actual]
        tables[table] = {
            "expected_partitions": len(expected),
            "partition_count": len(covered),
            "first_date": covered[0] if covered else None,
            "last_date": covered[-1] if covered else None,
            "missing_partitions": len(missing),
            "missing_dates": missing[:20],
            "empty_partitions": len(empty),
            "empty_dates": empty[:20],
            "invalid_partitions": invalid,
        }

        if table in {"daily_kline", "adj_factor"}:
            for date_value in calendar_dates:
                if date_value < table_start or date_value not in actual:
                    complete_for_open_t1[date_value] = False

    # A complete prefix requires both daily and adjustment partitions and a next-day open.
    daily_actual = _partition_dates(data_dir, "daily_kline")
    adjustment_actual = _partition_dates(data_dir, "adj_factor")
    daily_complete: dict[str, bool] = {}
    for date_value in calendar_dates:
        path = _partition_path(data_dir, "daily_kline", date_value)
        has_rows = False
        adjustment_path = _partition_path(data_dir, "adj_factor", date_value)
        if date_value in daily_actual and path.exists() and adjustment_path.exists():
            try:
                metadata = pq.ParquetFile(path).metadata
                adjustment_rows = pq.ParquetFile(adjustment_path).metadata.num_rows
                has_rows = (
                    metadata is not None
                    and metadata.num_rows > 0
                    and adjustment_rows > 0
                )
            except Exception:
                has_rows = False
        daily_complete[date_value] = (
            date_value in adjustment_actual and has_rows
        )
    open_t1_ready_through = _continuous_prefix(calendar_dates, daily_complete)
    if open_t1_ready_through is not None:
        next_dates = {
            date_value: index
            for index, date_value in enumerate(calendar_dates)
        }
        ready_index = next_dates[open_t1_ready_through]
        next_date = calendar_dates[ready_index + 1]
        try:
            open_frame = pd.read_parquet(
                _partition_path(data_dir, "daily_kline", next_date),
                columns=["open"],
            )
            if open_frame.empty or not open_frame["open"].notna().any():
                open_t1_ready_through = None
        except Exception:
            open_t1_ready_through = None

    report = {
        "start_date": start_date,
        "end_date": end_date,
        "trade_days": len(calendar_dates),
        "tables": tables,
        "open_t1_ready_through": open_t1_ready_through,
    }
    report["complete"] = all(
        table_report["missing_partitions"] == 0
        and table_report["empty_partitions"] == 0
        and not table_report["invalid_partitions"]
        for table_report in tables.values()
    )
    return report


def validate_stock_history(
    data_dir: Path,
    *,
    start_date: str = "20150101",
    end_date: str,
) -> dict[str, Any]:
    report = build_stock_history_coverage(
        data_dir,
        start_date=start_date,
        end_date=end_date,
        validate_partitions=True,
    )
    problems: list[str] = []
    for table, table_report in report["tables"].items():
        if table_report["missing_partitions"]:
            problems.append(
                f"{table}: missing {table_report['missing_partitions']} partitions"
            )
        if table_report["empty_partitions"]:
            problems.append(
                f"{table}: empty {table_report['empty_partitions']} partitions"
            )
        if table_report["invalid_partitions"]:
            problems.append(
                f"{table}: invalid {len(table_report['invalid_partitions'])} partitions"
            )
    if problems:
        raise RuntimeError("stock history coverage incomplete: " + "; ".join(problems))
    return report
