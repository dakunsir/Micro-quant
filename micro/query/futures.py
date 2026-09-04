import pandas as pd

from micro.catalog import (
    FT_LIMIT_SPEC,
    FUT_BASIC_SPEC,
    FUT_DAILY_SPEC,
    FUT_HOLDING_SPEC,
    FUT_INDEX_DAILY_SPEC,
    FUT_MAPPING_SPEC,
    FUT_MONTHLY_SPEC,
    FUT_SETTLE_SPEC,
    FUT_WEEKLY_DETAIL_SPEC,
    FUT_WEEKLY_SPEC,
    FUT_WSR_SPEC,
)
from micro.query import QueryContext
from micro.query.repository import (
    BaseParquetRepository,
    DailyPartitionRepository,
    eq_filter,
    in_filter,
)


def _daily_repo(ctx: QueryContext, spec) -> DailyPartitionRepository:
    return DailyPartitionRepository(ctx, spec)


def fut_basic(ctx: QueryContext, ts_code=None, exchange=None,
              fut_type=None, fut_code=None, fields=None,
              limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query futures contract specifications (symbol, exchange, multiplier, list/delist dates)."""
    repo = BaseParquetRepository(ctx, FUT_BASIC_SPEC)
    filters = []
    if ts_code is not None:
        filters.append(in_filter("ts_code", ts_code, FUT_BASIC_SPEC.columns))
    if exchange is not None:
        filters.append(eq_filter("exchange", exchange, FUT_BASIC_SPEC.columns))
    if fut_code is not None:
        filters.append(eq_filter("fut_code", fut_code, FUT_BASIC_SPEC.columns))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)


def fut_daily(ctx: QueryContext, ts_code=None, trade_date=None,
              start_date=None, end_date=None, fields=None,
              limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily OHLCV and open interest data for individual futures contracts."""
    return _daily_repo(ctx, FUT_DAILY_SPEC).query(
        ts_code, trade_date, start_date, end_date, fields, limit=limit, offset=offset
    )


def fut_holding(ctx: QueryContext, trade_date=None, symbol=None, start_date=None,
                end_date=None, exchange=None, fields=None,
                limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query top 20 broker long/short positions per futures contract (席位持仓)."""
    filters = []
    if symbol is not None:
        filters.append(eq_filter("symbol", symbol, FUT_HOLDING_SPEC.columns))
    if exchange is not None:
        filters.append(eq_filter("exchange", exchange, FUT_HOLDING_SPEC.columns))
    return _daily_repo(ctx, FUT_HOLDING_SPEC).query(
        None, trade_date, start_date, end_date, fields, filters=filters, limit=limit, offset=offset
    )


def fut_wsr(ctx: QueryContext, trade_date=None, symbol=None, start_date=None,
            end_date=None, exchange=None, fields=None,
            limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query futures warehouse stock receipt data (仓单数据)."""
    filters = []
    if symbol is not None:
        filters.append(eq_filter("symbol", symbol, FUT_WSR_SPEC.columns))
    if exchange is not None:
        filters.append(eq_filter("exchange", exchange, FUT_WSR_SPEC.columns))
    return _daily_repo(ctx, FUT_WSR_SPEC).query(
        None, trade_date, start_date, end_date, fields, filters=filters, limit=limit, offset=offset
    )


def fut_settle(ctx: QueryContext, ts_code=None, trade_date=None, start_date=None,
               end_date=None, exchange=None, fields=None,
               limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily settlement prices and open interest for futures contracts."""
    filters = [eq_filter("exchange", exchange, FUT_SETTLE_SPEC.columns)] if exchange is not None else []
    return _daily_repo(ctx, FUT_SETTLE_SPEC).query(
        ts_code, trade_date, start_date, end_date, fields, filters=filters, limit=limit, offset=offset
    )


def fut_mapping(ctx: QueryContext, ts_code=None, trade_date=None,
                start_date=None, end_date=None, fields=None,
                limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query main contract mapping: which specific contract was the main contract on each date."""
    return _daily_repo(ctx, FUT_MAPPING_SPEC).query(
        ts_code, trade_date, start_date, end_date, fields, limit=limit, offset=offset
    )


def ft_limit(ctx: QueryContext, ts_code=None, trade_date=None, start_date=None,
             end_date=None, exchange=None, fields=None,
             limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily price limits (up_limit, down_limit, pre_close) for futures contracts."""
    filters = [eq_filter("exchange", exchange, FT_LIMIT_SPEC.columns)] if exchange is not None else []
    return _daily_repo(ctx, FT_LIMIT_SPEC).query(
        ts_code, trade_date, start_date, end_date, fields, filters=filters, limit=limit, offset=offset
    )


def fut_weekly(ctx: QueryContext, ts_code=None, trade_date=None, start_date=None,
               end_date=None, exchange=None, fields=None,
               limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query weekly OHLCV and open interest bars for futures contracts."""
    filters = [eq_filter("exchange", exchange, FUT_WEEKLY_SPEC.columns)] if exchange is not None else []
    return _daily_repo(ctx, FUT_WEEKLY_SPEC).query(
        ts_code, trade_date, start_date, end_date, fields, filters=filters, limit=limit, offset=offset
    )


def fut_monthly(ctx: QueryContext, ts_code=None, trade_date=None, start_date=None,
                end_date=None, exchange=None, fields=None,
                limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query monthly OHLCV and open interest bars for futures contracts."""
    filters = [eq_filter("exchange", exchange, FUT_MONTHLY_SPEC.columns)] if exchange is not None else []
    return _daily_repo(ctx, FUT_MONTHLY_SPEC).query(
        ts_code, trade_date, start_date, end_date, fields, filters=filters, limit=limit, offset=offset
    )


def fut_index_daily(ctx: QueryContext, ts_code=None, trade_date=None,
                    start_date=None, end_date=None, fields=None,
                    limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily prices for continuous main contract index series."""
    return _daily_repo(ctx, FUT_INDEX_DAILY_SPEC).query(
        ts_code, trade_date, start_date, end_date, fields, limit=limit, offset=offset
    )


def fut_weekly_detail(ctx: QueryContext, exchange=None, prd=None,
                      start_date=None, end_date=None, fields=None,
                      limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query weekly COT-style long/short position breakdown by participant (龙虎榜周数据)."""
    filters = []
    if exchange is not None:
        filters.append(eq_filter("exchange", exchange, FUT_WEEKLY_DETAIL_SPEC.columns))
    if prd is not None:
        filters.append(eq_filter("prd", prd, FUT_WEEKLY_DETAIL_SPEC.columns))
    return _daily_repo(ctx, FUT_WEEKLY_DETAIL_SPEC).query(
        None, None, start_date, end_date, fields, filters=filters, limit=limit, offset=offset
    )
