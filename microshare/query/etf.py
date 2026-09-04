import pandas as pd

from microshare.catalog import (
    ETF_BASIC_SPEC,
    ETF_INDEX_SPEC,
    ETF_SH_CONS_SPEC,
    ETF_SHARE_SIZE_SPEC,
    FUND_ADJ_SPEC,
    FUND_DAILY_SPEC,
)
from microshare.query import QueryContext
from microshare.query.repository import BaseParquetRepository, DailyPartitionRepository, eq_filter, in_filter


def etf_basic(
    ctx: QueryContext,
    ts_code=None,
    index_code=None,
    list_date=None,
    list_status=None,
    exchange=None,
    mgr=None,
    mgr_name=None,
    limit: int | None = None,
    offset: int | None = None,
    fields=None,
) -> pd.DataFrame:
    """Query ETF basic information such as tracking index, manager, and listing status."""
    repo = BaseParquetRepository(ctx, ETF_BASIC_SPEC)
    filters = []
    if ts_code is not None:
        filters.append(in_filter("ts_code", ts_code, ETF_BASIC_SPEC.columns))
    if index_code is not None:
        filters.append(eq_filter("index_code", index_code, ETF_BASIC_SPEC.columns))
    if list_date is not None:
        filters.append(eq_filter("list_date", list_date, ETF_BASIC_SPEC.columns))
    if list_status is not None:
        filters.append(eq_filter("list_status", list_status, ETF_BASIC_SPEC.columns))
    if exchange is not None:
        filters.append(eq_filter("exchange", exchange, ETF_BASIC_SPEC.columns))
    if mgr is not None and mgr_name is not None and mgr != mgr_name:
        raise ValueError("mgr and mgr_name must match when both are provided")
    mgr_value = mgr_name if mgr_name is not None else mgr
    if mgr_value is not None:
        filters.append(eq_filter("mgr_name", mgr_value, ETF_BASIC_SPEC.columns))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)


def etf_index(
    ctx: QueryContext,
    ts_code=None,
    pub_date=None,
    base_date=None,
    limit: int | None = None,
    offset: int | None = None,
    fields=None,
) -> pd.DataFrame:
    """Query ETF benchmark index metadata."""
    repo = BaseParquetRepository(ctx, ETF_INDEX_SPEC)
    filters = []
    if ts_code is not None:
        filters.append(in_filter("ts_code", ts_code, ETF_INDEX_SPEC.columns))
    if pub_date is not None:
        filters.append(eq_filter("pub_date", pub_date, ETF_INDEX_SPEC.columns))
    if base_date is not None:
        filters.append(eq_filter("base_date", base_date, ETF_INDEX_SPEC.columns))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)


def fund_daily(
    ctx: QueryContext,
    ts_code=None,
    trade_date=None,
    start_date=None,
    end_date=None,
    limit: int | None = None,
    offset: int | None = None,
    fields=None,
) -> pd.DataFrame:
    """Query fund daily OHLCV data for ETF funds."""
    return DailyPartitionRepository(ctx, FUND_DAILY_SPEC).query(
        ts_code,
        trade_date,
        start_date,
        end_date,
        fields,
        limit=limit,
        offset=offset,
    )


def fund_adj(
    ctx: QueryContext,
    ts_code=None,
    trade_date=None,
    start_date=None,
    end_date=None,
    limit: int | None = None,
    offset: int | None = None,
    fields=None,
) -> pd.DataFrame:
    """Query fund adjustment factors for adjusted fund price calculations."""
    return DailyPartitionRepository(ctx, FUND_ADJ_SPEC).query(
        ts_code,
        trade_date,
        start_date,
        end_date,
        fields,
        limit=limit,
        offset=offset,
    )


def etf_share_size(
    ctx: QueryContext,
    ts_code=None,
    trade_date=None,
    start_date=None,
    end_date=None,
    exchange=None,
    limit: int | None = None,
    offset: int | None = None,
    fields=None,
) -> pd.DataFrame:
    """Query ETF daily share and scale data."""
    filters = []
    if exchange is not None:
        filters.append(eq_filter("exchange", exchange, ETF_SHARE_SIZE_SPEC.columns))
    return DailyPartitionRepository(ctx, ETF_SHARE_SIZE_SPEC).query(
        ts_code,
        trade_date,
        start_date,
        end_date,
        fields,
        filters=filters,
        limit=limit,
        offset=offset,
    )


def etf_sh_cons(
    ctx: QueryContext,
    ts_code=None,
    trade_date=None,
    con_code=None,
    start_date=None,
    end_date=None,
    limit: int | None = None,
    offset: int | None = None,
    fields=None,
) -> pd.DataFrame:
    """Query Shanghai ETF daily constituent portfolio data."""
    filters = []
    if con_code is not None:
        filters.append(eq_filter("con_code", con_code, ETF_SH_CONS_SPEC.columns))
    return DailyPartitionRepository(ctx, ETF_SH_CONS_SPEC).query(
        ts_code,
        trade_date,
        start_date,
        end_date,
        fields,
        filters=filters,
        limit=limit,
        offset=offset,
    )
