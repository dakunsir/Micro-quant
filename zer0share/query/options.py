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
from zer0share.schema import OPT_BASIC_COLS, OPT_DAILY_COLS


def opt_basic(ctx: QueryContext, ts_code=None, exchange=None, opt_code=None,
              call_put=None, name=None, list_date=None,
              limit: int | None = None, offset: int | None = None,
              fields=None) -> pd.DataFrame:
    """Query options contract specifications (strike, expiry, call/put, exercise type)."""
    repo = BaseParquetRepository(
        ctx,
        TableSpec(
            name="opt_basic",
            path_parts=("options", "opt_basic"),
            columns=OPT_BASIC_COLS,
            parquet_pattern="data.parquet",
            sync_table="opt_basic",
            order_by="ts_code",
        ),
    )
    filters = []
    if ts_code is not None:
        filters.append(in_filter("ts_code", ts_code, OPT_BASIC_COLS))
    if exchange is not None:
        filters.append(eq_filter("exchange", exchange, OPT_BASIC_COLS))
    if opt_code is not None:
        filters.append(eq_filter("opt_code", opt_code, OPT_BASIC_COLS))
    if call_put is not None:
        filters.append(eq_filter("call_put", call_put, OPT_BASIC_COLS))
    if name is not None:
        filters.append(eq_filter("name", name, OPT_BASIC_COLS))
    if list_date is not None:
        filters.append(eq_filter("list_date", list_date, OPT_BASIC_COLS))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)


def opt_daily(ctx: QueryContext, ts_code=None, trade_date=None, start_date=None,
              end_date=None, exchange=None,
              limit: int | None = None, offset: int | None = None,
              fields=None) -> pd.DataFrame:
    """Query daily OHLCV, settlement price, and open interest for options contracts."""
    filters = [eq_filter("exchange", exchange, OPT_DAILY_COLS)] if exchange is not None else []
    return DailyPartitionRepository(
        ctx,
        DailyTableSpec(
            name="opt_daily",
            path_parts=("options", "opt_daily"),
            columns=OPT_DAILY_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="opt_daily",
            order_by="ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
    ).query(ts_code, trade_date, start_date, end_date, fields, filters=filters, limit=limit, offset=offset)
