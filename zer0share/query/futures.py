import duckdb
import pandas as pd

from zer0share.query import QueryContext
from zer0share.query._helpers import parse_fields, query_daily_partitioned
from zer0share.schema import (
    FUT_BASIC_COLS, FUT_DAILY_COLS, FUT_HOLDING_COLS, FUT_WSR_COLS,
    FUT_SETTLE_COLS, FUT_MAPPING_COLS, FT_LIMIT_COLS, FUT_WEEKLY_COLS,
    FUT_MONTHLY_COLS, FUT_INDEX_DAILY_COLS, FUT_WEEKLY_DETAIL_COLS,
)


def fut_basic(ctx: QueryContext, ts_code=None, exchange=None,
              fut_type=None, fut_code=None, fields=None,
              limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query futures contract specifications (symbol, exchange, multiplier, list/delist dates)."""
    table_dir = ctx.data_dir / "futures" / "fut_basic"
    if not table_dir.exists():
        raise FileNotFoundError(
            "fut_basic data not found; run `python main.py sync --table fut_basic` first"
        )
    selected = parse_fields(fields, FUT_BASIC_COLS)
    where = []
    params = []
    if ts_code is not None:
        codes = [c.strip() for c in ts_code.split(",") if c.strip()]
        placeholders = ", ".join("?" for _ in codes)
        where.append(f"ts_code IN ({placeholders})"); params.extend(codes)
    if exchange is not None:
        where.append("exchange = ?"); params.append(exchange)
    if fut_code is not None:
        where.append("fut_code = ?"); params.append(fut_code)

    pattern = table_dir / "date=*" / "data.parquet"
    sql = (
        f"SELECT {', '.join(selected)} "
        "FROM read_parquet(?, hive_partitioning=true, union_by_name=true)"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ts_code"
    if limit is not None:
        sql += " LIMIT ?"; params.append(limit)
    if offset is not None:
        sql += " OFFSET ?"; params.append(offset)
    return duckdb.connect().execute(sql, [str(pattern), *params]).fetchdf()


def fut_daily(ctx: QueryContext, ts_code=None, trade_date=None,
              start_date=None, end_date=None, fields=None,
              limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily OHLCV and open interest data for individual futures contracts."""
    return query_daily_partitioned(
        ctx, "fut_daily", "fut_daily", FUT_DAILY_COLS,
        ts_code, trade_date, start_date, end_date, fields,
        data_dir_override=ctx.data_dir / "futures",
        limit=limit, offset=offset,
    )


def fut_holding(ctx: QueryContext, trade_date=None, symbol=None, start_date=None,
                end_date=None, exchange=None, fields=None,
                limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query top 20 broker long/short positions per futures contract (席位持仓)."""
    extra = {}
    if symbol is not None:
        extra["symbol"] = symbol
    if exchange is not None:
        extra["exchange"] = exchange
    return query_daily_partitioned(
        ctx, "fut_holding", "fut_holding", FUT_HOLDING_COLS,
        None, trade_date, start_date, end_date, fields,
        extra_filters=extra or None,
        data_dir_override=ctx.data_dir / "futures",
        order_by="trade_date, symbol, broker",
        limit=limit, offset=offset,
    )


def fut_wsr(ctx: QueryContext, trade_date=None, symbol=None, start_date=None,
            end_date=None, exchange=None, fields=None,
            limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query futures warehouse stock receipt data (仓单数据)."""
    extra = {}
    if symbol is not None:
        extra["symbol"] = symbol
    if exchange is not None:
        extra["exchange"] = exchange
    return query_daily_partitioned(
        ctx, "fut_wsr", "fut_wsr", FUT_WSR_COLS,
        None, trade_date, start_date, end_date, fields,
        extra_filters=extra or None,
        data_dir_override=ctx.data_dir / "futures",
        order_by="trade_date, symbol, warehouse",
        limit=limit, offset=offset,
    )


def fut_settle(ctx: QueryContext, ts_code=None, trade_date=None, start_date=None,
               end_date=None, exchange=None, fields=None,
               limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily settlement prices and open interest for futures contracts."""
    extra = {"exchange": exchange} if exchange is not None else None
    return query_daily_partitioned(
        ctx, "fut_settle", "fut_settle", FUT_SETTLE_COLS,
        ts_code, trade_date, start_date, end_date, fields,
        extra_filters=extra,
        data_dir_override=ctx.data_dir / "futures",
        limit=limit, offset=offset,
    )


def fut_mapping(ctx: QueryContext, ts_code=None, trade_date=None,
                start_date=None, end_date=None, fields=None,
                limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query main contract mapping: which specific contract was the main contract on each date."""
    return query_daily_partitioned(
        ctx, "fut_mapping", "fut_mapping", FUT_MAPPING_COLS,
        ts_code, trade_date, start_date, end_date, fields,
        data_dir_override=ctx.data_dir / "futures",
        order_by="ts_code, trade_date",
        limit=limit, offset=offset,
    )


def ft_limit(ctx: QueryContext, ts_code=None, trade_date=None, start_date=None,
             end_date=None, exchange=None, fields=None,
             limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily price limits (up_limit, down_limit, pre_close) for futures contracts."""
    extra = {"exchange": exchange} if exchange is not None else None
    return query_daily_partitioned(
        ctx, "ft_limit", "ft_limit", FT_LIMIT_COLS,
        ts_code, trade_date, start_date, end_date, fields,
        extra_filters=extra,
        data_dir_override=ctx.data_dir / "futures",
        limit=limit, offset=offset,
    )


def fut_weekly(ctx: QueryContext, ts_code=None, trade_date=None, start_date=None,
               end_date=None, exchange=None, fields=None,
               limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query weekly OHLCV and open interest bars for futures contracts."""
    extra = {"exchange": exchange} if exchange is not None else None
    return query_daily_partitioned(
        ctx, "fut_weekly", "fut_weekly", FUT_WEEKLY_COLS,
        ts_code, trade_date, start_date, end_date, fields,
        extra_filters=extra,
        data_dir_override=ctx.data_dir / "futures",
        limit=limit, offset=offset,
    )


def fut_monthly(ctx: QueryContext, ts_code=None, trade_date=None, start_date=None,
                end_date=None, exchange=None, fields=None,
                limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query monthly OHLCV and open interest bars for futures contracts."""
    extra = {"exchange": exchange} if exchange is not None else None
    return query_daily_partitioned(
        ctx, "fut_monthly", "fut_monthly", FUT_MONTHLY_COLS,
        ts_code, trade_date, start_date, end_date, fields,
        extra_filters=extra,
        data_dir_override=ctx.data_dir / "futures",
        limit=limit, offset=offset,
    )


def fut_index_daily(ctx: QueryContext, ts_code=None, trade_date=None,
                    start_date=None, end_date=None, fields=None,
                    limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily prices for continuous main contract index series."""
    return query_daily_partitioned(
        ctx, "fut_index_daily", "fut_index_daily", FUT_INDEX_DAILY_COLS,
        ts_code, trade_date, start_date, end_date, fields,
        data_dir_override=ctx.data_dir / "futures",
        limit=limit, offset=offset,
    )


def fut_weekly_detail(ctx: QueryContext, exchange=None, prd=None,
                      start_date=None, end_date=None, fields=None,
                      limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query weekly COT-style long/short position breakdown by participant (龙虎榜周数据)."""
    extra = {}
    if exchange is not None:
        extra["exchange"] = exchange
    if prd is not None:
        extra["prd"] = prd
    return query_daily_partitioned(
        ctx, "fut_weekly_detail", "fut_weekly_detail", FUT_WEEKLY_DETAIL_COLS,
        None, None, start_date, end_date, fields,
        extra_filters=extra or None,
        data_dir_override=ctx.data_dir / "futures",
        order_by="date, exchange, prd",
        limit=limit, offset=offset,
    )
