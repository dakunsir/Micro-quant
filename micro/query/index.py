import pandas as pd

from micro.catalog import IDX_ANNS_SPEC, INDEX_DAILY_SPEC, INDEX_WEIGHT_SPEC, SW_DAILY_SPEC
from micro.query import QueryContext
from micro.query.repository import (
    BaseParquetRepository,
    DailyPartitionRepository,
    SqlFilter,
    date_range_filters,
    eq_filter,
)


def _base_repo(ctx: QueryContext, spec) -> BaseParquetRepository:
    return BaseParquetRepository(ctx, spec)


def _daily_repo(ctx: QueryContext, spec) -> DailyPartitionRepository:
    return DailyPartitionRepository(ctx, spec)


def index_daily(ctx: QueryContext, ts_code=None, trade_date=None,
                start_date=None, end_date=None, fields=None,
                limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily OHLCV bar data for broad market indices (SSE/SZSE/CSI)."""
    return _daily_repo(ctx, INDEX_DAILY_SPEC).query(
        ts_code, trade_date, start_date, end_date, fields, limit=limit, offset=offset
    )


def index_weight(ctx: QueryContext, index_code=None, trade_date=None,
                 start_date=None, end_date=None, fields=None,
                 limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query constituent weights for CSI 300/500/1000 index rebalancing dates."""
    repo = _base_repo(ctx, INDEX_WEIGHT_SPEC)
    filters: list[SqlFilter] = []
    if index_code is not None:
        filters.append(eq_filter("index_code", index_code, INDEX_WEIGHT_SPEC.columns))
    filters.extend(date_range_filters("trade_date", trade_date, start_date, end_date, INDEX_WEIGHT_SPEC.columns))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)


def sw_daily(ctx: QueryContext, ts_code=None, trade_date=None,
             start_date=None, end_date=None, fields=None,
             limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily OHLCV bar data for Shenwan industry indices."""
    return _daily_repo(ctx, SW_DAILY_SPEC).query(
        ts_code, trade_date, start_date, end_date, fields, limit=limit, offset=offset
    )


def idx_anns(
    ctx: QueryContext,
    ann_date=None,
    start_date=None,
    end_date=None,
    src=None,
    limit: int | None = None,
    offset: int | None = None,
    fields=None,
) -> pd.DataFrame:
    """Query local index-company announcements."""
    repo = _daily_repo(ctx, IDX_ANNS_SPEC)
    filters: list[SqlFilter] = []
    if src is not None:
        filters.append(eq_filter("source", src, IDX_ANNS_SPEC.columns))
    return repo.query(
        trade_date=ann_date,
        start_date=start_date,
        end_date=end_date,
        fields=fields,
        filters=filters,
        limit=limit,
        offset=offset,
    )
