import duckdb
import pandas as pd

from zer0share.query import QueryContext
from zer0share.query._helpers import (
    format_date_columns, parse_date, parse_fields, query_daily_partitioned,
)
from zer0share.schema import (
    BASIC_COLS, DAILY_COLS, ADJ_FACTOR_COLS, DAILY_BASIC_COLS,
    STOCK_ST_COLS, SUSPEND_D_COLS, STK_LIMIT_COLS,
    INDEX_WEIGHT_COLS, INDEX_DAILY_COLS,
)

UNIVERSE_COLS = ["trade_date", "universe", "ts_code"]


def stock_basic(ctx: QueryContext, ts_code=None, name=None, market=None,
                list_status="L", exchange=None, is_hs=None, fields=None,
                limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query stock basic info (name, market, list_status, etc.)."""
    path = ctx.data_dir / "basic" / "data.parquet"
    if not path.exists():
        raise FileNotFoundError("basic data not found; run `python main.py sync --table basic` first")

    columns = parse_fields(fields, BASIC_COLS)
    where = []
    params = []
    if ts_code is not None:
        where.append("ts_code = ?"); params.append(ts_code)
    if name is not None:
        where.append("name = ?"); params.append(name)
    if market is not None:
        where.append("market = ?"); params.append(market)
    if list_status is not None:
        where.append("list_status = ?"); params.append(list_status)
    if exchange is not None:
        where.append("exchange = ?"); params.append(exchange)
    if is_hs is not None:
        where.append("is_hs = ?"); params.append(is_hs)

    sql = f"SELECT {', '.join(columns)} FROM read_parquet(?)"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ts_code"
    if limit is not None:
        sql += " LIMIT ?"; params.append(limit)
    if offset is not None:
        sql += " OFFSET ?"; params.append(offset)
    return duckdb.connect().execute(sql, [str(path), *params]).fetchdf()


def daily(ctx: QueryContext, ts_code=None, trade_date=None,
          start_date=None, end_date=None, fields=None,
          limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily OHLCV bar data (open, high, low, close, vol, amount)."""
    return query_daily_partitioned(
        ctx, "daily_kline", "daily_kline", DAILY_COLS,
        ts_code, trade_date, start_date, end_date, fields,
        limit=limit, offset=offset,
    )


def adj_factor(ctx: QueryContext, ts_code=None, trade_date=None,
               start_date=None, end_date=None, fields=None,
               limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query back-adjustment factors for split/dividend-adjusted price calculation."""
    return query_daily_partitioned(
        ctx, "adj_factor", "adj_factor", ADJ_FACTOR_COLS,
        ts_code, trade_date, start_date, end_date, fields,
        limit=limit, offset=offset,
    )


def daily_basic(ctx: QueryContext, ts_code=None, trade_date=None,
                start_date=None, end_date=None, fields=None,
                limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily fundamental indicators (PE, PB, market cap, turnover rate, etc.)."""
    return query_daily_partitioned(
        ctx, "daily_basic", "daily_basic", DAILY_BASIC_COLS,
        ts_code, trade_date, start_date, end_date, fields,
        limit=limit, offset=offset,
    )


def stock_st(ctx: QueryContext, ts_code=None, trade_date=None,
             start_date=None, end_date=None, fields=None,
             limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query ST/ST*/delisting-risk flag history per stock per trading day."""
    return query_daily_partitioned(
        ctx, "stock_st", "stock_st", STOCK_ST_COLS,
        ts_code, trade_date, start_date, end_date, fields,
        limit=limit, offset=offset,
    )


def suspend_d(ctx: QueryContext, ts_code=None, trade_date=None,
              start_date=None, end_date=None, fields=None,
              limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily suspension records (stock halted from trading)."""
    return query_daily_partitioned(
        ctx, "suspend_d", "suspend_d", SUSPEND_D_COLS,
        ts_code, trade_date, start_date, end_date, fields,
        limit=limit, offset=offset,
    )


def stk_limit(ctx: QueryContext, ts_code=None, trade_date=None,
              start_date=None, end_date=None, fields=None,
              limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily price limits (up_limit, down_limit, pre_close) per stock."""
    return query_daily_partitioned(
        ctx, "stk_limit", "stk_limit", STK_LIMIT_COLS,
        ts_code, trade_date, start_date, end_date, fields,
        limit=limit, offset=offset,
    )


def index_daily(ctx: QueryContext, ts_code=None, trade_date=None,
                start_date=None, end_date=None, fields=None,
                limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query daily OHLCV bar data for broad market indices (SSE/SZSE/CSI)."""
    return query_daily_partitioned(
        ctx, "index_daily", "index_daily", INDEX_DAILY_COLS,
        ts_code, trade_date, start_date, end_date, fields,
        limit=limit, offset=offset,
    )


def index_weight(ctx: QueryContext, index_code=None, trade_date=None,
                 start_date=None, end_date=None, fields=None,
                 limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query constituent weights for CSI 300/500/1000 index rebalancing dates."""
    if trade_date is not None and (start_date is not None or end_date is not None):
        raise ValueError("trade_date cannot be combined with start_date or end_date")
    parsed_start = parse_date(start_date) if start_date is not None else None
    parsed_end = parse_date(end_date) if end_date is not None else None
    if parsed_start is not None and parsed_end is not None and parsed_end < parsed_start:
        raise ValueError("end_date must be on or after start_date")

    table_dir = ctx.data_dir / "index_weight"
    if not table_dir.exists():
        raise FileNotFoundError(
            "index_weight data not found; run `python main.py sync --table index_weight` first"
        )

    selected = parse_fields(fields, INDEX_WEIGHT_COLS)
    where = []
    params = []
    if index_code is not None:
        where.append("index_code = ?"); params.append(index_code)
    if trade_date is not None:
        where.append("trade_date = ?"); params.append(parse_date(trade_date).strftime("%Y%m%d"))
    if parsed_start is not None:
        where.append("trade_date >= ?"); params.append(parsed_start.strftime("%Y%m%d"))
    if parsed_end is not None:
        where.append("trade_date <= ?"); params.append(parsed_end.strftime("%Y%m%d"))

    pattern = table_dir / "index_code=*" / "date=*" / "data.parquet"
    sql = (
        f"SELECT {', '.join(selected)} "
        "FROM read_parquet(?, hive_partitioning=true, union_by_name=true)"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY index_code, con_code, trade_date"
    if limit is not None:
        sql += " LIMIT ?"; params.append(limit)
    if offset is not None:
        sql += " OFFSET ?"; params.append(offset)
    return duckdb.connect().execute(sql, [str(pattern), *params]).fetchdf()


def universe(ctx: QueryContext, universe=None, ts_code=None, trade_date=None,
             start_date=None, end_date=None, fields=None,
             limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query universe membership snapshots (which stocks belong to which universe on each date)."""
    if trade_date is not None and (start_date is not None or end_date is not None):
        raise ValueError("trade_date cannot be combined with start_date or end_date")
    parsed_start = parse_date(start_date) if start_date is not None else None
    parsed_end = parse_date(end_date) if end_date is not None else None
    if parsed_start is not None and parsed_end is not None and parsed_end < parsed_start:
        raise ValueError("end_date must be on or after start_date")

    table_dir = ctx.data_dir / "universe"
    if not table_dir.exists():
        raise FileNotFoundError("universe data not found; run `python main.py build-universe` first")

    selected = parse_fields(fields, UNIVERSE_COLS)
    where = []
    params = []
    if universe is not None:
        where.append("universe = ?"); params.append(universe)
    if ts_code is not None:
        codes = [c.strip() for c in ts_code.split(",") if c.strip()]
        placeholders = ", ".join("?" for _ in codes)
        where.append(f"ts_code IN ({placeholders})"); params.extend(codes)
    if trade_date is not None:
        parse_date(trade_date)
        where.append("trade_date = ?"); params.append(trade_date)
    if parsed_start is not None:
        where.append("trade_date >= ?"); params.append(start_date)
    if parsed_end is not None:
        where.append("trade_date <= ?"); params.append(end_date)

    pattern = table_dir / "name=*" / "date=*" / "data.parquet"
    sql = (
        f"SELECT {', '.join(selected)} "
        "FROM read_parquet(?, hive_partitioning=true, union_by_name=true)"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY universe, ts_code, trade_date"
    if limit is not None:
        sql += " LIMIT ?"; params.append(limit)
    if offset is not None:
        sql += " OFFSET ?"; params.append(offset)
    df = duckdb.connect().execute(sql, [str(pattern), *params]).fetchdf()
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
