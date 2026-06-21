from pathlib import Path

import duckdb
import pandas as pd

from zer0share.query import QueryContext
from zer0share.query.repository import SqlFilter, date_range_filters, in_filter


TABLE_COLUMNS = [
    "order_book_id",
    "datetime",
    "open",
    "close",
    "high",
    "low",
    "limit_up",
    "limit_down",
    "total_turnover",
    "volume",
    "num_trades",
    "prev_close",
    "trade_date",
]

BASIC_COLUMNS = [
    "order_book_id",
    "symbol",
    "type",
    "market",
    "status",
]


def _parse_fields(fields):
    if fields is None:
        return None
    if isinstance(fields, str):
        return [item.strip() for item in fields.split(",") if item.strip()]
    return list(fields)


def _source(ctx: QueryContext) -> Path:
    return ctx.data_dir / "ricequant" / "stock_minute" / "date=*" / "data.parquet"


def _basic_source(ctx: QueryContext) -> Path:
    return ctx.data_dir / "ricequant" / "basic" / "data.parquet"


def _ensure_exists(ctx: QueryContext) -> None:
    table_dir = ctx.data_dir / "ricequant" / "stock_minute"
    if not table_dir.exists():
        raise FileNotFoundError(
            "ricequant_stock_minute data not found; run `python main.py sync --table ricequant_stock_minute` first"
        )


def _ensure_basic_exists(ctx: QueryContext) -> None:
    if not _basic_source(ctx).exists():
        raise FileNotFoundError(
            "ricequant_basic data not found; run `python main.py sync --table ricequant_basic` first"
        )


def get_price(
    ctx: QueryContext,
    order_book_ids,
    start_date=None,
    end_date=None,
    fields=None,
    limit: int | None = None,
    offset: int | None = None,
) -> pd.DataFrame:
    _ensure_exists(ctx)
    parsed_fields = _parse_fields(fields)
    selected = "*" if parsed_fields is None else ", ".join(parsed_fields)
    filters: list[SqlFilter] = []
    if order_book_ids is not None:
        filters.append(in_filter("order_book_id", order_book_ids, TABLE_COLUMNS))
    filters.extend(date_range_filters("trade_date", None, start_date, end_date, TABLE_COLUMNS))

    sql = f"SELECT {selected} FROM read_parquet(?, hive_partitioning=true, union_by_name=true)"
    params: list[object] = [str(_source(ctx))]
    if filters:
        sql += " WHERE " + " AND ".join(f.clause for f in filters)
        for filt in filters:
            params.extend(filt.params)
    sql += " ORDER BY order_book_id, datetime"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    if offset is not None:
        sql += " OFFSET ?"
        params.append(offset)
    return duckdb.connect().execute(sql, params).fetchdf()


def all_instruments(
    ctx: QueryContext,
    type=None,
    market="cn",
    fields=None,
    limit: int | None = None,
    offset: int | None = None,
) -> pd.DataFrame:
    _ensure_basic_exists(ctx)
    parsed_fields = _parse_fields(fields)
    selected = "*" if parsed_fields is None else ", ".join(parsed_fields)
    filters: list[SqlFilter] = []
    if type is not None:
        filters.append(SqlFilter("type = ?", (type,)))
    if market is not None:
        filters.append(SqlFilter("market = ?", (market,)))
    sql = f"SELECT {selected} FROM read_parquet(?)"
    params: list[object] = [str(_basic_source(ctx))]
    if filters:
        sql += " WHERE " + " AND ".join(f.clause for f in filters)
        for filt in filters:
            params.extend(filt.params)
    sql += " ORDER BY order_book_id"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    if offset is not None:
        sql += " OFFSET ?"
        params.append(offset)
    return duckdb.connect().execute(sql, params).fetchdf()
