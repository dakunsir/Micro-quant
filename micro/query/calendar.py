import pandas as pd

from micro.query import QueryContext
from micro.query._helpers import parse_is_open
from micro.query.repository import (
    BaseParquetRepository,
    SqlFilter,
    TableSpec,
    date_range_filters,
    eq_filter,
)
from micro.schema import TRADE_CAL_COLS


def trade_cal(
    ctx: QueryContext,
    exchange: str = "SSE",
    start_date=None,
    end_date=None,
    is_open=None,
    fields=None,
    limit: int | None = None,
    offset: int | None = None,
) -> pd.DataFrame:
    """Query trading calendar. Returns cal_date, is_open, pretrade_date per exchange."""
    repo = BaseParquetRepository(
        ctx,
        TableSpec(
            name="trade_cal",
            path_parts=("stock", "trade_cal"),
            columns=TRADE_CAL_COLS,
            parquet_pattern="exchange=*/data.parquet",
            sync_table="trade_cal",
            order_by="exchange, cal_date",
            hive_partitioning=True,
        ),
    )
    filters: list[SqlFilter] = [eq_filter("exchange", exchange, TRADE_CAL_COLS)]
    filters.extend(date_range_filters("cal_date", None, start_date, end_date, TRADE_CAL_COLS))
    if is_open is not None:
        filters.append(eq_filter("is_open", parse_is_open(is_open), TRADE_CAL_COLS))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)
