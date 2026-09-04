import pandas as pd

from microshare.catalog import OPT_BASIC_SPEC, OPT_DAILY_SPEC
from microshare.query import QueryContext
from microshare.query.repository import (
    BaseParquetRepository,
    DailyPartitionRepository,
    eq_filter,
    in_filter,
)


def opt_basic(ctx: QueryContext, ts_code=None, exchange=None, opt_code=None,
              call_put=None, name=None, list_date=None,
              limit: int | None = None, offset: int | None = None,
              fields=None) -> pd.DataFrame:
    """Query options contract specifications (strike, expiry, call/put, exercise type)."""
    repo = BaseParquetRepository(ctx, OPT_BASIC_SPEC)
    filters = []
    if ts_code is not None:
        filters.append(in_filter("ts_code", ts_code, OPT_BASIC_SPEC.columns))
    if exchange is not None:
        filters.append(eq_filter("exchange", exchange, OPT_BASIC_SPEC.columns))
    if opt_code is not None:
        filters.append(eq_filter("opt_code", opt_code, OPT_BASIC_SPEC.columns))
    if call_put is not None:
        filters.append(eq_filter("call_put", call_put, OPT_BASIC_SPEC.columns))
    if name is not None:
        filters.append(eq_filter("name", name, OPT_BASIC_SPEC.columns))
    if list_date is not None:
        filters.append(eq_filter("list_date", list_date, OPT_BASIC_SPEC.columns))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)


def opt_daily(ctx: QueryContext, ts_code=None, trade_date=None, start_date=None,
              end_date=None, exchange=None,
              limit: int | None = None, offset: int | None = None,
              fields=None) -> pd.DataFrame:
    """Query daily OHLCV, settlement price, and open interest for options contracts."""
    filters = [eq_filter("exchange", exchange, OPT_DAILY_SPEC.columns)] if exchange is not None else []
    return DailyPartitionRepository(ctx, OPT_DAILY_SPEC).query(
        ts_code, trade_date, start_date, end_date, fields, filters=filters, limit=limit, offset=offset
    )
