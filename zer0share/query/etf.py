import pandas as pd

from zer0share.catalog import ETF_BASIC_SPEC
from zer0share.query import QueryContext
from zer0share.query.repository import BaseParquetRepository, eq_filter, in_filter


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
