import re
import datetime as dt
from pathlib import Path

import duckdb
import pandas as pd

from zer0share.query import QueryContext


def parse_fields(fields, default_columns: list[str]) -> list[str]:
    if fields is None:
        return list(default_columns)
    if isinstance(fields, str):
        parsed = [f.strip() for f in fields.split(",") if f.strip()]
    else:
        parsed = list(fields)
    unknown = [f for f in parsed if f not in default_columns]
    if unknown:
        raise ValueError(f"unknown fields: {', '.join(unknown)}")
    return parsed


def parse_date(value: str):
    try:
        return dt.datetime.strptime(value, "%Y%m%d").date()
    except ValueError as e:
        raise ValueError(f"invalid date format: {value}; expected YYYYMMDD") from e


def parse_is_open(value) -> bool:
    if isinstance(value, bool):
        return value
    if value in (1, "1"):
        return True
    if value in (0, "0"):
        return False
    raise ValueError("is_open must be one of True, False, 1, 0, '1', or '0'")


def format_date_columns(df: pd.DataFrame, date_columns: list[str]) -> pd.DataFrame:
    for column in date_columns:
        if column not in df.columns:
            continue
        formatted = pd.to_datetime(df[column], errors="coerce").dt.strftime("%Y%m%d")
        df[column] = formatted.astype(object)
        df.loc[formatted.isna(), column] = None
    return df


def query_daily_partitioned(
    ctx: QueryContext,
    table_name: str,
    sync_table: str,
    columns: list[str],
    ts_code,
    trade_date,
    start_date,
    end_date,
    fields,
    extra_filters: dict | None = None,
    data_dir_override: Path | None = None,
    order_by: str = "ts_code, trade_date",
    limit: int | None = None,
    offset: int | None = None,
) -> pd.DataFrame:
    if trade_date is not None and (start_date is not None or end_date is not None):
        raise ValueError("trade_date cannot be combined with start_date or end_date")
    parsed_start = parse_date(start_date) if start_date is not None else None
    parsed_end = parse_date(end_date) if end_date is not None else None
    if parsed_start is not None and parsed_end is not None and parsed_end < parsed_start:
        raise ValueError("end_date must be on or after start_date")

    base_dir = data_dir_override or ctx.data_dir
    table_dir = base_dir / table_name
    if not table_dir.exists():
        raise FileNotFoundError(
            f"{sync_table} data not found; run `python main.py sync --table {sync_table}` first"
        )

    selected = parse_fields(fields, columns)
    where = []
    params = []
    if ts_code is not None:
        codes = [c.strip() for c in ts_code.split(",") if c.strip()]
        placeholders = ", ".join("?" for _ in codes)
        where.append(f"ts_code IN ({placeholders})")
        params.extend(codes)
    if trade_date is not None:
        where.append("trade_date = ?")
        params.append(parse_date(trade_date).strftime("%Y%m%d"))
    if parsed_start is not None:
        where.append("trade_date >= ?")
        params.append(parsed_start.strftime("%Y%m%d"))
    if parsed_end is not None:
        where.append("trade_date <= ?")
        params.append(parsed_end.strftime("%Y%m%d"))
    if extra_filters is not None:
        for col, val in extra_filters.items():
            if col not in columns:
                raise ValueError(f"unknown filter column: {col}")
            where.append(f"{col} = ?")
            params.append(val)

    if not re.match(r"^[\w]+(?:\s+(?:ASC|DESC))?(?:,\s*[\w]+(?:\s+(?:ASC|DESC))?)*$", order_by, re.IGNORECASE):
        raise ValueError(f"invalid order_by: {order_by!r}")

    pattern = table_dir / "date=*" / "data.parquet"
    sql = (
        f"SELECT {', '.join(selected)} "
        "FROM read_parquet(?, hive_partitioning=true, union_by_name=true)"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY {order_by}"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    if offset is not None:
        sql += " OFFSET ?"
        params.append(offset)

    return duckdb.connect().execute(sql, [str(pattern), *params]).fetchdf()
