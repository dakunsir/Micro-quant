import pandas as pd

from zer0share.query import QueryContext
from zer0share.query.repository import (
    BaseParquetRepository,
    DailyPartitionRepository,
    DailyTableSpec,
    TableSpec,
    eq_filter,
    in_filter,
)
from zer0share.schema import (
    FT_LIMIT_COLS,
    FUT_BASIC_COLS,
    FUT_DAILY_COLS,
    FUT_HOLDING_COLS,
    FUT_INDEX_DAILY_COLS,
    FUT_MAPPING_COLS,
    FUT_MONTHLY_COLS,
    FUT_SETTLE_COLS,
    FUT_WEEKLY_COLS,
    FUT_WEEKLY_DETAIL_COLS,
    FUT_WSR_COLS,
)


def _daily_repo(ctx: QueryContext, spec: DailyTableSpec) -> DailyPartitionRepository:
    return DailyPartitionRepository(ctx, spec)


def fut_basic(ctx: QueryContext, ts_code=None, exchange=None,
              fut_type=None, fut_code=None, fields=None,
              limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query futures contract specifications (symbol, exchange, multiplier, list/delist dates)."""
    repo = BaseParquetRepository(
        ctx,
        TableSpec(
            name="fut_basic",
            path_parts=("futures", "fut_basic"),
            columns=FUT_BASIC_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="fut_basic",
            order_by="ts_code",
            hive_partitioning=True,
            union_by_name=True,
        ),
    )
    filters = []
    if ts_code is not None:
        filters.append(in_filter("ts_code", ts_code, FUT_BASIC_COLS))
    if exchange is not None:
        filters.append(eq_filter("exchange", exchange, FUT_BASIC_COLS))
    if fut_code is not None:
        filters.append(eq_filter("fut_code", fut_code, FUT_BASIC_COLS))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)


def fut_daily(ctx: QueryContext, ts_code=None, trade_date=None,
              start_date=None, end_date=None, fields=None,
              limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily OHLCV and open interest data for individual futures contracts."""
    return _daily_repo(
        ctx,
        DailyTableSpec(
            name="fut_daily",
            path_parts=("futures", "fut_daily"),
            columns=FUT_DAILY_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="fut_daily",
            order_by="ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
    ).query(ts_code, trade_date, start_date, end_date, fields, limit=limit, offset=offset)


def fut_holding(ctx: QueryContext, trade_date=None, symbol=None, start_date=None,
                end_date=None, exchange=None, fields=None,
                limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query top 20 broker long/short positions per futures contract (席位持仓)."""
    filters = []
    if symbol is not None:
        filters.append(eq_filter("symbol", symbol, FUT_HOLDING_COLS))
    if exchange is not None:
        filters.append(eq_filter("exchange", exchange, FUT_HOLDING_COLS))
    return _daily_repo(
        ctx,
        DailyTableSpec(
            name="fut_holding",
            path_parts=("futures", "fut_holding"),
            columns=FUT_HOLDING_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="fut_holding",
            order_by="trade_date, symbol, broker",
            hive_partitioning=True,
            union_by_name=True,
            code_column=None,
        ),
    ).query(None, trade_date, start_date, end_date, fields, filters=filters, limit=limit, offset=offset)


def fut_wsr(ctx: QueryContext, trade_date=None, symbol=None, start_date=None,
            end_date=None, exchange=None, fields=None,
            limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query futures warehouse stock receipt data (仓单数据)."""
    filters = []
    if symbol is not None:
        filters.append(eq_filter("symbol", symbol, FUT_WSR_COLS))
    if exchange is not None:
        filters.append(eq_filter("exchange", exchange, FUT_WSR_COLS))
    return _daily_repo(
        ctx,
        DailyTableSpec(
            name="fut_wsr",
            path_parts=("futures", "fut_wsr"),
            columns=FUT_WSR_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="fut_wsr",
            order_by="trade_date, symbol, warehouse",
            hive_partitioning=True,
            union_by_name=True,
            code_column=None,
        ),
    ).query(None, trade_date, start_date, end_date, fields, filters=filters, limit=limit, offset=offset)


def fut_settle(ctx: QueryContext, ts_code=None, trade_date=None, start_date=None,
               end_date=None, exchange=None, fields=None,
               limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily settlement prices and open interest for futures contracts."""
    filters = [eq_filter("exchange", exchange, FUT_SETTLE_COLS)] if exchange is not None else []
    return _daily_repo(
        ctx,
        DailyTableSpec(
            name="fut_settle",
            path_parts=("futures", "fut_settle"),
            columns=FUT_SETTLE_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="fut_settle",
            order_by="ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
    ).query(ts_code, trade_date, start_date, end_date, fields, filters=filters, limit=limit, offset=offset)


def fut_mapping(ctx: QueryContext, ts_code=None, trade_date=None,
                start_date=None, end_date=None, fields=None,
                limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query main contract mapping: which specific contract was the main contract on each date."""
    return _daily_repo(
        ctx,
        DailyTableSpec(
            name="fut_mapping",
            path_parts=("futures", "fut_mapping"),
            columns=FUT_MAPPING_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="fut_mapping",
            order_by="ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
    ).query(ts_code, trade_date, start_date, end_date, fields, limit=limit, offset=offset)


def ft_limit(ctx: QueryContext, ts_code=None, trade_date=None, start_date=None,
             end_date=None, exchange=None, fields=None,
             limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily price limits (up_limit, down_limit, pre_close) for futures contracts."""
    filters = [eq_filter("exchange", exchange, FT_LIMIT_COLS)] if exchange is not None else []
    return _daily_repo(
        ctx,
        DailyTableSpec(
            name="ft_limit",
            path_parts=("futures", "ft_limit"),
            columns=FT_LIMIT_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="ft_limit",
            order_by="ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
    ).query(ts_code, trade_date, start_date, end_date, fields, filters=filters, limit=limit, offset=offset)


def fut_weekly(ctx: QueryContext, ts_code=None, trade_date=None, start_date=None,
               end_date=None, exchange=None, fields=None,
               limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query weekly OHLCV and open interest bars for futures contracts."""
    filters = [eq_filter("exchange", exchange, FUT_WEEKLY_COLS)] if exchange is not None else []
    return _daily_repo(
        ctx,
        DailyTableSpec(
            name="fut_weekly",
            path_parts=("futures", "fut_weekly"),
            columns=FUT_WEEKLY_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="fut_weekly",
            order_by="ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
    ).query(ts_code, trade_date, start_date, end_date, fields, filters=filters, limit=limit, offset=offset)


def fut_monthly(ctx: QueryContext, ts_code=None, trade_date=None, start_date=None,
                end_date=None, exchange=None, fields=None,
                limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query monthly OHLCV and open interest bars for futures contracts."""
    filters = [eq_filter("exchange", exchange, FUT_MONTHLY_COLS)] if exchange is not None else []
    return _daily_repo(
        ctx,
        DailyTableSpec(
            name="fut_monthly",
            path_parts=("futures", "fut_monthly"),
            columns=FUT_MONTHLY_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="fut_monthly",
            order_by="ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
    ).query(ts_code, trade_date, start_date, end_date, fields, filters=filters, limit=limit, offset=offset)


def fut_index_daily(ctx: QueryContext, ts_code=None, trade_date=None,
                    start_date=None, end_date=None, fields=None,
                    limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily prices for continuous main contract index series."""
    return _daily_repo(
        ctx,
        DailyTableSpec(
            name="fut_index_daily",
            path_parts=("futures", "fut_index_daily"),
            columns=FUT_INDEX_DAILY_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="fut_index_daily",
            order_by="ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
    ).query(ts_code, trade_date, start_date, end_date, fields, limit=limit, offset=offset)


def fut_weekly_detail(ctx: QueryContext, exchange=None, prd=None,
                      start_date=None, end_date=None, fields=None,
                      limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query weekly COT-style long/short position breakdown by participant (龙虎榜周数据)."""
    filters = []
    if exchange is not None:
        filters.append(eq_filter("exchange", exchange, FUT_WEEKLY_DETAIL_COLS))
    if prd is not None:
        filters.append(eq_filter("prd", prd, FUT_WEEKLY_DETAIL_COLS))
    return _daily_repo(
        ctx,
        DailyTableSpec(
            name="fut_weekly_detail",
            path_parts=("futures", "fut_weekly_detail"),
            columns=FUT_WEEKLY_DETAIL_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="fut_weekly_detail",
            order_by="week_date, exchange, prd",
            hive_partitioning=True,
            union_by_name=True,
            date_column="week_date",
            code_column=None,
        ),
    ).query(None, None, start_date, end_date, fields, filters=filters, limit=limit, offset=offset)
