#!/usr/bin/env python3
"""Quality checks for local RiceQuant stock minute parquet partitions."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import duckdb

try:
    from microshare.config import load_config
except ImportError:  # pragma: no cover - allows running from unusual paths
    load_config = None


REQUIRED_COLUMNS = {
    "order_book_id",
    "datetime",
    "total_turnover",
    "close",
    "low",
    "volume",
    "high",
    "num_trades",
    "open",
    "trade_date",
    "date",
}

DATE_DIR_RE = re.compile(r"^date=(\d{8})$")


@dataclass(frozen=True)
class Partition:
    trade_date: str
    path: Path
    parquet: Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="检查 data/ricequant/stock_minute 分区 parquet 的基础质量。"
    )
    parser.add_argument(
        "--stock-minute-dir",
        type=Path,
        help="stock_minute 目录，默认读取 config/settings.toml 的 data_dir/ricequant/stock_minute。",
    )
    parser.add_argument(
        "--start-date",
        help="只检查不早于该日期的分区，格式 YYYYMMDD。",
    )
    parser.add_argument(
        "--end-date",
        help="只检查不晚于该日期的分区，格式 YYYYMMDD。",
    )
    parser.add_argument(
        "--expected-start",
        help="期望起始日期，格式 YYYYMMDD；不传则用实际最早分区。",
    )
    parser.add_argument(
        "--expected-end",
        help="期望结束日期，格式 YYYYMMDD；不传则用实际最晚分区。",
    )
    parser.add_argument(
        "--min-rows-per-day",
        type=int,
        default=100_000,
        help="单日最小行数阈值，低于该值视为异常；默认 100000。",
    )
    parser.add_argument(
        "--show-limit",
        type=int,
        default=20,
        help="每类异常最多展示多少行；默认 20。",
    )
    parser.add_argument(
        "--skip-calendar",
        action="store_true",
        help="跳过本地 trade_cal 交易日覆盖检查。",
    )
    return parser


def resolve_stock_minute_dir(arg: Path | None) -> Path:
    if arg is not None:
        return arg
    if load_config is not None:
        try:
            return load_config().data_dir / "ricequant" / "stock_minute"
        except Exception:
            pass
    return Path("data/ricequant/stock_minute")


def validate_date(value: str | None, name: str) -> None:
    if value is not None and not re.fullmatch(r"\d{8}", value):
        raise SystemExit(f"{name} 必须是 YYYYMMDD，得到: {value!r}")


def discover_partitions(
    stock_minute_dir: Path,
    start_date: str | None,
    end_date: str | None,
) -> tuple[list[Partition], list[Path]]:
    partitions: list[Partition] = []
    invalid_dirs: list[Path] = []

    for child in sorted(stock_minute_dir.iterdir()):
        if not child.is_dir():
            continue
        match = DATE_DIR_RE.match(child.name)
        if match is None:
            invalid_dirs.append(child)
            continue
        trade_date = match.group(1)
        if start_date is not None and trade_date < start_date:
            continue
        if end_date is not None and trade_date > end_date:
            continue
        partitions.append(
            Partition(
                trade_date=trade_date,
                path=child,
                parquet=child / "data.parquet",
            )
        )
    return partitions, invalid_dirs


def print_list(title: str, values: list[str], limit: int) -> None:
    print(f"{title}: {len(values)}")
    for value in values[:limit]:
        print(f"  {value}")
    if len(values) > limit:
        print(f"  ... 还有 {len(values) - limit} 条")


def check_files(partitions: list[Partition]) -> tuple[list[str], list[str]]:
    missing = []
    empty = []
    for partition in partitions:
        if not partition.parquet.exists():
            missing.append(str(partition.parquet))
        elif partition.parquet.stat().st_size == 0:
            empty.append(str(partition.parquet))
    return missing, empty


def parquet_source(stock_minute_dir: Path, start_date: str | None, end_date: str | None) -> str:
    if start_date is None and end_date is None:
        glob = repr(str(stock_minute_dir / "date=*" / "data.parquet"))
        return f"read_parquet({glob}, filename=true)"
    files = []
    partitions, _ = discover_partitions(stock_minute_dir, start_date, end_date)
    for partition in partitions:
        if partition.parquet.exists() and partition.parquet.stat().st_size > 0:
            files.append(str(partition.parquet))
    if not files:
        raise SystemExit("指定范围内没有可读的 data.parquet 文件。")
    file_list = "[" + ",".join(repr(path) for path in files) + "]"
    return f"read_parquet({file_list}, filename=true)"


def fetch_df(conn: duckdb.DuckDBPyConnection, query: str):
    return conn.execute(query).fetchdf()


def check_schema(conn: duckdb.DuckDBPyConnection, source: str) -> list[str]:
    df = fetch_df(conn, f"describe select * from {source}")
    columns = set(df["column_name"].tolist())
    return sorted(REQUIRED_COLUMNS - columns)


def print_dataframe(title: str, df, limit: int) -> None:
    print(f"{title}: {len(df)}")
    if len(df) > 0:
        print(df.head(limit).to_string(index=False))
        if len(df) > limit:
            print(f"... 还有 {len(df) - limit} 行")


def check_calendar(
    conn: duckdb.DuckDBPyConnection,
    stock_minute_dir: Path,
    start_date: str,
    end_date: str,
) -> list[str]:
    data_dir = stock_minute_dir.parent.parent
    cal_path = data_dir / "stock" / "trade_cal" / "exchange=SSE" / "data.parquet"
    if not cal_path.exists():
        print(f"交易日历检查: 跳过，未找到 {cal_path}")
        return []

    query = f"""
        with expected as (
            select cal_date
            from '{cal_path}'
            where is_open = true
              and cal_date between '{start_date}' and '{end_date}'
        ),
        actual as (
            select regexp_extract(filename, 'date=([0-9]{{8}})', 1) as trade_date
            from '{stock_minute_dir / "date=*" / "data.parquet"}'
            group by 1
        )
        select expected.cal_date
        from expected
        left join actual on actual.trade_date = expected.cal_date
        where actual.trade_date is null
        order by expected.cal_date
    """
    return [row[0] for row in conn.execute(query).fetchall()]


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    for name in ("start_date", "end_date", "expected_start", "expected_end"):
        validate_date(getattr(args, name), "--" + name.replace("_", "-"))

    stock_minute_dir = resolve_stock_minute_dir(args.stock_minute_dir)
    if not stock_minute_dir.exists():
        print(f"stock_minute 目录不存在: {stock_minute_dir}", file=sys.stderr)
        return 2

    partitions, invalid_dirs = discover_partitions(
        stock_minute_dir,
        args.start_date,
        args.end_date,
    )
    if not partitions:
        print("没有发现符合条件的 date=YYYYMMDD 分区。", file=sys.stderr)
        return 2

    actual_start = partitions[0].trade_date
    actual_end = partitions[-1].trade_date
    expected_start = args.expected_start or actual_start
    expected_end = args.expected_end or actual_end

    print("=== stock_minute 数据质检 ===")
    print(f"目录: {stock_minute_dir}")
    print(f"分区范围: {actual_start} ~ {actual_end}")
    print(f"分区数量: {len(partitions)}")
    print(f"期望范围: {expected_start} ~ {expected_end}")

    errors = 0
    warnings = 0

    if actual_start != expected_start:
        print(f"ERROR: 实际起始分区 {actual_start} != 期望 {expected_start}")
        errors += 1
    if actual_end != expected_end:
        print(f"ERROR: 实际结束分区 {actual_end} != 期望 {expected_end}")
        errors += 1

    invalid_dir_names = [str(path) for path in invalid_dirs]
    print_list("非标准分区目录", invalid_dir_names, args.show_limit)
    if invalid_dir_names:
        warnings += len(invalid_dir_names)

    missing_files, empty_files = check_files(partitions)
    print_list("缺失 data.parquet", missing_files, args.show_limit)
    print_list("0 字节 data.parquet", empty_files, args.show_limit)
    errors += len(missing_files) + len(empty_files)

    source = parquet_source(stock_minute_dir, args.start_date, args.end_date)
    conn = duckdb.connect()
    try:
        missing_columns = check_schema(conn, source)
        print_list("缺失必要字段", missing_columns, args.show_limit)
        errors += len(missing_columns)

        if missing_columns:
            print("字段不完整，跳过内容级检查。")
        else:
            summary = fetch_df(
                conn,
                f"""
                select
                    min(datetime) as min_datetime,
                    max(datetime) as max_datetime,
                    min(trade_date) as min_trade_date,
                    max(trade_date) as max_trade_date,
                    min(date) as min_date,
                    max(date) as max_date,
                    count(*) as row_count,
                    count(distinct trade_date) as trade_dates,
                    count(distinct order_book_id) as symbols
                from {source}
                """,
            )
            print("\n总体摘要:")
            print(summary.to_string(index=False))

            daily = fetch_df(
                conn,
                f"""
                select
                    regexp_extract(filename, 'date=([0-9]{{8}})', 1) as partition_date,
                    count(*) as row_count,
                    count(distinct order_book_id) as symbols,
                    min(datetime) as min_datetime,
                    max(datetime) as max_datetime,
                    min(trade_date) as min_trade_date,
                    max(trade_date) as max_trade_date,
                    sum(case when trade_date != regexp_extract(filename, 'date=([0-9]{{8}})', 1) then 1 else 0 end) as wrong_trade_date_rows,
                    sum(case when date != cast(regexp_extract(filename, 'date=([0-9]{{8}})', 1) as bigint) then 1 else 0 end) as wrong_date_rows,
                    sum(case when datetime is null or order_book_id is null then 1 else 0 end) as null_key_rows,
                    sum(case when cast(datetime as time) < time '09:31:00' or cast(datetime as time) > time '15:00:00' then 1 else 0 end) as out_of_session_rows
                from {source}
                group by 1
                order by 1
                """,
            )

            low_rows = daily[daily["row_count"] < args.min_rows_per_day]
            wrong_dates = daily[
                (daily["wrong_trade_date_rows"] > 0) | (daily["wrong_date_rows"] > 0)
            ]
            null_keys = daily[daily["null_key_rows"] > 0]
            out_of_session = daily[daily["out_of_session_rows"] > 0]

            print_dataframe(
                f"\n单日行数低于 {args.min_rows_per_day}",
                low_rows,
                args.show_limit,
            )
            print_dataframe("\n分区日期与字段日期不一致", wrong_dates, args.show_limit)
            print_dataframe("\n关键字段为空", null_keys, args.show_limit)
            print_dataframe("\n非 09:31~15:00 时间行", out_of_session, args.show_limit)
            errors += len(wrong_dates) + len(null_keys) + len(out_of_session)
            warnings += len(low_rows)

            if not args.skip_calendar:
                missing_calendar_days = check_calendar(
                    conn,
                    stock_minute_dir,
                    expected_start,
                    expected_end,
                )
                print_list("交易日历中存在但 stock_minute 缺失的日期", missing_calendar_days, args.show_limit)
                errors += len(missing_calendar_days)
    except Exception as exc:
        print(f"ERROR: parquet 内容检查失败: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()

    print("\n=== 结果 ===")
    print(f"errors: {errors}")
    print(f"warnings: {warnings}")
    if errors:
        print("FAIL")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
