import pandas as pd

from microshare.query import QueryContext
from microshare.query.repository import BaseParquetRepository, TableSpec, eq_filter, in_filter
from microshare.schema import CI_MEMBER_COLS, SW_CLASSIFY_COLS, SW_MEMBER_COLS


def index_classify(ctx: QueryContext, index_code=None, level=None, src=None,
                   parent_code=None, fields=None,
                   limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query Shenwan (SW) industry classification hierarchy (L1/L2/L3 levels)."""
    repo = BaseParquetRepository(
        ctx,
        TableSpec(
            name="sw_classify",
            path_parts=("stock", "industry", "sw_classify"),
            columns=SW_CLASSIFY_COLS,
            parquet_pattern="data.parquet",
            sync_table="industry",
            order_by="industry_code",
        ),
    )
    filters = []
    if index_code is not None:
        filters.append(eq_filter("index_code", index_code, SW_CLASSIFY_COLS))
    if level is not None:
        filters.append(eq_filter("level", level, SW_CLASSIFY_COLS))
    if src is not None:
        filters.append(eq_filter("src", src, SW_CLASSIFY_COLS))
    if parent_code is not None:
        filters.append(eq_filter("parent_code", parent_code, SW_CLASSIFY_COLS))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)


def index_member_all(ctx: QueryContext, l1_code=None, l2_code=None, l3_code=None,
                     ts_code=None, is_new=None, fields=None,
                     limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query Shenwan industry membership: which stocks belong to which SW industry."""
    repo = BaseParquetRepository(
        ctx,
        TableSpec(
            name="sw_member",
            path_parts=("stock", "industry", "sw_member"),
            columns=SW_MEMBER_COLS,
            parquet_pattern="data.parquet",
            sync_table="industry",
            order_by="ts_code, l1_code",
        ),
    )
    filters = []
    if l1_code is not None:
        filters.append(eq_filter("l1_code", l1_code, SW_MEMBER_COLS))
    if l2_code is not None:
        filters.append(eq_filter("l2_code", l2_code, SW_MEMBER_COLS))
    if l3_code is not None:
        filters.append(eq_filter("l3_code", l3_code, SW_MEMBER_COLS))
    if ts_code is not None:
        filters.append(in_filter("ts_code", ts_code, SW_MEMBER_COLS))
    if is_new is not None:
        filters.append(eq_filter("is_new", is_new, SW_MEMBER_COLS))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)


def ci_index_member(ctx: QueryContext, l1_code=None, l2_code=None, l3_code=None,
                    ts_code=None, is_new=None, fields=None,
                    limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query China Securities Index (CI) industry membership."""
    repo = BaseParquetRepository(
        ctx,
        TableSpec(
            name="ci_member",
            path_parts=("stock", "industry", "ci_member"),
            columns=CI_MEMBER_COLS,
            parquet_pattern="data.parquet",
            sync_table="ci_member",
            order_by="ts_code, l1_code",
        ),
    )
    filters = []
    if l1_code is not None:
        filters.append(eq_filter("l1_code", l1_code, CI_MEMBER_COLS))
    if l2_code is not None:
        filters.append(eq_filter("l2_code", l2_code, CI_MEMBER_COLS))
    if l3_code is not None:
        filters.append(eq_filter("l3_code", l3_code, CI_MEMBER_COLS))
    if ts_code is not None:
        filters.append(in_filter("ts_code", ts_code, CI_MEMBER_COLS))
    if is_new is not None:
        filters.append(eq_filter("is_new", is_new, CI_MEMBER_COLS))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)
