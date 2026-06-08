"""
Integrity smoke test for daily_kline local Parquet data.

Checks:
  1. Partition count matches trade calendar
  2. No dates in disk that are not in the calendar
  3. No empty Parquet files
  4. Row counts grow monotonically across sampled years
  5. Required columns present and non-null on a sample date
"""
from __future__ import annotations

import argparse
import os
import sys

import duckdb

from zer0share import pro_api
from zer0share.config import load_config

REQUIRED_COLS = {"ts_code", "trade_date", "open", "high", "low", "close", "vol", "amount"}

SAMPLE_YEARS = ["1990", "1993", "1999", "2005", "2010", "2015", "2020", "2025"]


def _fail(msg: str) -> None:
    print(f"  FAIL  {msg}")


def _ok(msg: str) -> None:
    print(f"  OK    {msg}")


def run_integrity(start_date: str, end_date: str, empty_size_threshold: int, max_missing: int) -> int:
    cfg = load_config()
    data_dir = cfg.data_dir / "stock" / "daily_kline"

    if not data_dir.exists():
        print(f"FAIL: data directory not found: {data_dir}", file=sys.stderr)
        print("Run: uv run python main.py sync --table daily_kline", file=sys.stderr)
        return 1

    # ── 1. collect disk partitions ────────────────────────────────────────
    disk_dates = sorted(
        d.replace("date=", "")
        for d in os.listdir(data_dir)
        if d.startswith("date=")
    )
    if not disk_dates:
        print("FAIL: no partitions found on disk", file=sys.stderr)
        return 1

    actual_start = disk_dates[0]
    actual_end   = disk_dates[-1]
    print(f"\n[daily_kline integrity]  range={actual_start}~{actual_end}  partitions={len(disk_dates)}")

    con = duckdb.connect(str(cfg.db_path))

    cal = con.execute(f"""
        SELECT strftime(cal_date, '%Y%m%d') AS cal_date FROM trade_cal
        WHERE exchange='SSE' AND is_open=1
          AND cal_date BETWEEN DATE '{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}'
                           AND DATE '{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}'
        ORDER BY cal_date
    """).fetchdf()
    cal_dates = set(cal["cal_date"].tolist())
    disk_set  = set(disk_dates)

    # ── 2. calendar vs disk ───────────────────────────────────────────────
    print("\n[1] Calendar vs disk")
    missing = sorted(cal_dates - disk_set)
    extra   = sorted(disk_set - cal_dates)

    if missing and len(missing) > max_missing:
        _fail(f"{len(missing)} trading day(s) missing from disk (allowed={max_missing}): {missing[:10]}")
    elif missing:
        print(f"  WARN  {len(missing)} trading day(s) missing (within allowed={max_missing}, likely Tushare gaps): {missing}")
    else:
        _ok("no missing trading days")

    if extra:
        _fail(f"{len(extra)} disk partition(s) not in calendar: {extra[:5]}")
    else:
        _ok("no extra partitions outside calendar")

    # ── 3. empty Parquet files ────────────────────────────────────────────
    print("\n[2] Empty Parquet files")
    empty = [
        (d, os.path.getsize(data_dir / f"date={d}" / "data.parquet"))
        for d in disk_dates
        if os.path.getsize(data_dir / f"date={d}" / "data.parquet") < empty_size_threshold
    ]
    if empty:
        _fail(f"{len(empty)} suspiciously small file(s) (< {empty_size_threshold} bytes):")
        for dt, sz in empty[:5]:
            print(f"        {dt}: {sz} bytes")
    else:
        _ok(f"all {len(disk_dates)} files above {empty_size_threshold}-byte threshold")

    # ── 4. row counts grow over sampled years ────────────────────────────
    print("\n[3] Row count by year (spot check)")
    prev_rows = 0
    prev_year = None
    errors = 0
    for year in SAMPLE_YEARS:
        year_dates = [d for d in disk_dates if d.startswith(year)]
        if not year_dates:
            print(f"        {year}: no data (skipped)")
            continue
        path = data_dir / f"date={year_dates[0]}" / "data.parquet"
        rows = duckdb.execute(f"SELECT COUNT(*) FROM read_parquet('{path}')").fetchone()[0]
        status = ""
        if prev_rows and rows < prev_rows * 0.5:
            status = f"  <-- unexpected drop from {prev_rows}"
            errors += 1
        print(f"        {year_dates[0]}: {rows:>5} rows{status}")
        prev_rows = rows
        prev_year = year

    if errors:
        _fail(f"{errors} unexpected row-count drop(s) across years")
    else:
        _ok("row counts look healthy across sampled years")

    # ── 5. required columns on latest date ───────────────────────────────
    print("\n[4] Required columns on latest partition")
    latest_path = data_dir / f"date={disk_dates[-1]}" / "data.parquet"
    df = duckdb.execute(f"SELECT * FROM read_parquet('{latest_path}') LIMIT 5").fetchdf()
    actual_cols = set(df.columns)
    missing_cols = REQUIRED_COLS - actual_cols
    if missing_cols:
        _fail(f"missing columns: {missing_cols}")
    else:
        _ok(f"all required columns present ({len(actual_cols)} total)")

    null_cols = [c for c in REQUIRED_COLS if c in actual_cols and df[c].isnull().any()]
    if null_cols:
        _fail(f"null values in: {null_cols}")
    else:
        _ok("no nulls in required columns on sample rows")

    # ── 6. pro_api round-trip ─────────────────────────────────────────────
    print("\n[5] pro_api round-trip")
    pro = pro_api()
    result = pro.daily(trade_date=disk_dates[-1], limit=3)
    if result.empty:
        _fail(f"pro.daily(trade_date={disk_dates[-1]}) returned empty")
    else:
        _ok(f"pro.daily(trade_date={disk_dates[-1]}) returned {len(result)} rows")

    print()
    failures = (len(missing) > max_missing) or extra or empty or missing_cols or null_cols or errors
    if failures:
        print("Result: FAILED")
        return 1
    print("Result: PASSED")
    return 0


def _yyyymmdd(s: str) -> str:
    s = s.replace("-", "")
    if len(s) != 8 or not s.isdigit():
        raise argparse.ArgumentTypeError(f"expected YYYYMMDD, got {s!r}")
    return s


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Integrity smoke test for daily_kline synced Parquet data."
    )
    parser.add_argument("--start-date", default="19901219", type=_yyyymmdd,
                        help="earliest date to check against trade calendar (YYYYMMDD)")
    parser.add_argument("--end-date", default="20260605", type=_yyyymmdd,
                        help="latest date to check against trade calendar (YYYYMMDD)")
    parser.add_argument("--empty-threshold", type=int, default=500,
                        help="file size in bytes below which a parquet is flagged as empty")
    parser.add_argument("--max-missing", type=int, default=10,
                        help="tolerated number of missing trading days (Tushare source gaps)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run_integrity(
        start_date=args.start_date,
        end_date=args.end_date,
        empty_size_threshold=args.empty_threshold,
        max_missing=args.max_missing,
    )


if __name__ == "__main__":
    raise SystemExit(main())
