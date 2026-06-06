import pandas as pd

from zer0share.query import QueryContext
from zer0share.query._helpers import format_date_columns
from zer0share.query.repository import (
    BaseParquetRepository,
    DailyPartitionRepository,
    DailyTableSpec,
    SqlFilter,
    TableSpec,
    date_range_filters,
    eq_filter,
    in_filter,
)
from zer0share.schema import (
    ADJ_FACTOR_COLS,
    BASIC_COLS,
    DAILY_BASIC_COLS,
    DAILY_COLS,
    INDEX_DAILY_COLS,
    INDEX_WEIGHT_COLS,
    STOCK_ST_COLS,
    STK_LIMIT_COLS,
    SUSPEND_D_COLS,
)

UNIVERSE_COLS = ["trade_date", "universe", "ts_code"]


def _base_repo(ctx: QueryContext, spec: TableSpec) -> BaseParquetRepository:
    return BaseParquetRepository(ctx, spec)


def _daily_repo(ctx: QueryContext, spec: DailyTableSpec) -> DailyPartitionRepository:
    return DailyPartitionRepository(ctx, spec)


def stock_basic(ctx: QueryContext, ts_code=None, name=None, market=None,
                list_status="L", exchange=None, is_hs=None, fields=None,
                limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query stock basic info (name, market, list_status, etc.)."""
    repo = _base_repo(
        ctx,
        TableSpec(
            name="basic",
            path_parts=("basic",),
            columns=BASIC_COLS,
            parquet_pattern="data.parquet",
            sync_table="basic",
            order_by="ts_code",
        ),
    )
    filters = []
    if ts_code is not None:
        filters.append(eq_filter("ts_code", ts_code, BASIC_COLS))
    if name is not None:
        filters.append(eq_filter("name", name, BASIC_COLS))
    if market is not None:
        filters.append(eq_filter("market", market, BASIC_COLS))
    if list_status is not None:
        filters.append(eq_filter("list_status", list_status, BASIC_COLS))
    if exchange is not None:
        filters.append(eq_filter("exchange", exchange, BASIC_COLS))
    if is_hs is not None:
        filters.append(eq_filter("is_hs", is_hs, BASIC_COLS))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)


def daily(ctx: QueryContext, ts_code=None, trade_date=None,
          start_date=None, end_date=None, fields=None,
          limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily OHLCV bar data (open, high, low, close, vol, amount)."""
    return _daily_repo(
        ctx,
        DailyTableSpec(
            name="daily_kline",
            path_parts=("daily_kline",),
            columns=DAILY_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="daily_kline",
            order_by="ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
    ).query(ts_code, trade_date, start_date, end_date, fields, limit=limit, offset=offset)


def adj_factor(ctx: QueryContext, ts_code=None, trade_date=None,
               start_date=None, end_date=None, fields=None,
               limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query back-adjustment factors for split/dividend-adjusted price calculation."""
    return _daily_repo(
        ctx,
        DailyTableSpec(
            name="adj_factor",
            path_parts=("adj_factor",),
            columns=ADJ_FACTOR_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="adj_factor",
            order_by="ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
    ).query(ts_code, trade_date, start_date, end_date, fields, limit=limit, offset=offset)


def daily_basic(ctx: QueryContext, ts_code=None, trade_date=None,
                start_date=None, end_date=None, fields=None,
                limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily fundamental indicators (PE, PB, market cap, turnover rate, etc.)."""
    return _daily_repo(
        ctx,
        DailyTableSpec(
            name="daily_basic",
            path_parts=("daily_basic",),
            columns=DAILY_BASIC_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="daily_basic",
            order_by="ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
    ).query(ts_code, trade_date, start_date, end_date, fields, limit=limit, offset=offset)


def stock_st(ctx: QueryContext, ts_code=None, trade_date=None,
             start_date=None, end_date=None, fields=None,
             limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query ST/ST*/delisting-risk flag history per stock per trading day."""
    return _daily_repo(
        ctx,
        DailyTableSpec(
            name="stock_st",
            path_parts=("stock_st",),
            columns=STOCK_ST_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="stock_st",
            order_by="ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
    ).query(ts_code, trade_date, start_date, end_date, fields, limit=limit, offset=offset)


def suspend_d(ctx: QueryContext, ts_code=None, trade_date=None,
              start_date=None, end_date=None, fields=None,
              limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily suspension records (stock halted from trading)."""
    return _daily_repo(
        ctx,
        DailyTableSpec(
            name="suspend_d",
            path_parts=("suspend_d",),
            columns=SUSPEND_D_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="suspend_d",
            order_by="ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
    ).query(ts_code, trade_date, start_date, end_date, fields, limit=limit, offset=offset)


def stk_limit(ctx: QueryContext, ts_code=None, trade_date=None,
              start_date=None, end_date=None, fields=None,
              limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily price limits (up_limit, down_limit, pre_close) per stock."""
    return _daily_repo(
        ctx,
        DailyTableSpec(
            name="stk_limit",
            path_parts=("stk_limit",),
            columns=STK_LIMIT_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="stk_limit",
            order_by="ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
    ).query(ts_code, trade_date, start_date, end_date, fields, limit=limit, offset=offset)


def index_daily(ctx: QueryContext, ts_code=None, trade_date=None,
                start_date=None, end_date=None, fields=None,
                limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily OHLCV bar data for broad market indices (SSE/SZSE/CSI)."""
    return _daily_repo(
        ctx,
        DailyTableSpec(
            name="index_daily",
            path_parts=("index_daily",),
            columns=INDEX_DAILY_COLS,
            parquet_pattern="date=*/data.parquet",
            sync_table="index_daily",
            order_by="ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
    ).query(ts_code, trade_date, start_date, end_date, fields, limit=limit, offset=offset)


def index_weight(ctx: QueryContext, index_code=None, trade_date=None,
                 start_date=None, end_date=None, fields=None,
                 limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query constituent weights for CSI 300/500/1000 index rebalancing dates."""
    repo = _base_repo(
        ctx,
        TableSpec(
            name="index_weight",
            path_parts=("index_weight",),
            columns=INDEX_WEIGHT_COLS,
            parquet_pattern="index_code=*/date=*/data.parquet",
            sync_table="index_weight",
            order_by="index_code, con_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
    )
    filters: list[SqlFilter] = []
    if index_code is not None:
        filters.append(eq_filter("index_code", index_code, INDEX_WEIGHT_COLS))
    filters.extend(date_range_filters("trade_date", trade_date, start_date, end_date, INDEX_WEIGHT_COLS))
    return repo.query(fields=fields, filters=filters, limit=limit, offset=offset)


def universe(ctx: QueryContext, universe=None, ts_code=None, trade_date=None,
             start_date=None, end_date=None, fields=None,
             limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query universe membership snapshots (which stocks belong to which universe on each date)."""
    repo = _base_repo(
        ctx,
        TableSpec(
            name="universe",
            path_parts=("universe",),
            columns=UNIVERSE_COLS,
            parquet_pattern="name=*/date=*/data.parquet",
            sync_table="build-universe",
            order_by="universe, ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
    )
    filters: list[SqlFilter] = []
    if universe is not None:
        filters.append(eq_filter("universe", universe, UNIVERSE_COLS))
    if ts_code is not None:
        filters.append(in_filter("ts_code", ts_code, UNIVERSE_COLS))
    filters.extend(date_range_filters("trade_date", trade_date, start_date, end_date, UNIVERSE_COLS))
    df = repo.query(fields=fields, filters=filters, limit=limit, offset=offset)
    return format_date_columns(df, ["trade_date"])


def pro_bar(ctx: QueryContext, ts_code: str, start_date=None, end_date=None,
            asset: str = "E", adj=None, freq: str = "D", trade_date=None,
            ma=None, limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query adjusted OHLCV bars; adj='qfq' for forward-adjusted, 'hfq' for back-adjusted."""
    if asset != "E":
        raise NotImplementedError("local pro_bar currently only supports asset='E'")
    if freq != "D":
        raise NotImplementedError("local pro_bar currently only supports freq='D'")
    if ma:
        raise NotImplementedError("local pro_bar does not support ma yet")
    if adj not in (None, "qfq", "hfq"):
        raise ValueError("adj must be one of None, 'qfq', or 'hfq'")

    daily_df = daily(ctx, ts_code=ts_code, trade_date=trade_date,
                     start_date=start_date, end_date=end_date)
    if adj is None or daily_df.empty:
        result = daily_df
    else:
        factors = adj_factor(ctx, ts_code=ts_code, trade_date=trade_date,
                             start_date=start_date, end_date=end_date)
        if factors.empty:
            result = daily_df.iloc[0:0].copy()
        else:
            result = daily_df.merge(
                factors[["ts_code", "trade_date", "adj_factor"]],
                on=["ts_code", "trade_date"], how="left",
            ).sort_values(["ts_code", "trade_date"])
            result["adj_factor"] = result.groupby("ts_code")["adj_factor"].bfill()
            result = result.dropna(subset=["adj_factor"])
            if result.empty:
                result = daily_df.iloc[0:0].copy()
            else:
                price_columns = ["open", "high", "low", "close", "pre_close"]
                if adj == "qfq":
                    base_factor = result.groupby("ts_code")["adj_factor"].transform("last")
                    multiplier = result["adj_factor"] / base_factor
                else:
                    multiplier = result["adj_factor"]
                for col in price_columns:
                    result[col] = (result[col] * multiplier).round(2)
                result["change"] = (result["close"] - result["pre_close"]).round(2)
                result["pct_chg"] = (result["change"] / result["pre_close"] * 100).round(2)
                result = result.drop(columns=["adj_factor"])

    if offset is not None:
        result = result.iloc[offset:]
    if limit is not None:
        result = result.iloc[:limit]
    return result
