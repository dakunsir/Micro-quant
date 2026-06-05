import duckdb
import pandas as pd

from zer0share.query import QueryContext
from zer0share.query._helpers import parse_fields, query_daily_partitioned
from zer0share.schema import OPT_BASIC_COLS, OPT_DAILY_COLS


def opt_basic(ctx: QueryContext, ts_code=None, exchange=None, opt_code=None,
              call_put=None, name=None, list_date=None,
              limit: int | None = None, offset: int | None = None,
              fields=None) -> pd.DataFrame:
    """Query options contract specifications (strike, expiry, call/put, exercise type)."""
    path = ctx.data_dir / "options" / "opt_basic" / "data.parquet"
    if not path.exists():
        raise FileNotFoundError(
            "opt_basic data not found; run `python main.py sync --table opt_basic` first"
        )
    selected = parse_fields(fields, OPT_BASIC_COLS)
    where = []
    params = []
    if ts_code is not None:
        codes = [c.strip() for c in ts_code.split(",") if c.strip()]
        placeholders = ", ".join("?" for _ in codes)
        where.append(f"ts_code IN ({placeholders})"); params.extend(codes)
    if exchange is not None:
        where.append("exchange = ?"); params.append(exchange)
    if opt_code is not None:
        where.append("opt_code = ?"); params.append(opt_code)
    if call_put is not None:
        where.append("call_put = ?"); params.append(call_put)
    if name is not None:
        where.append("name = ?"); params.append(name)
    if list_date is not None:
        where.append("list_date = ?"); params.append(list_date)

    sql = f"SELECT {', '.join(selected)} FROM read_parquet(?)"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ts_code"
    if limit is not None:
        sql += " LIMIT ?"; params.append(limit)
    if offset is not None:
        sql += " OFFSET ?"; params.append(offset)
    return duckdb.connect().execute(sql, [str(path), *params]).fetchdf()


def opt_daily(ctx: QueryContext, ts_code=None, trade_date=None, start_date=None,
              end_date=None, exchange=None,
              limit: int | None = None, offset: int | None = None,
              fields=None) -> pd.DataFrame:
    """Query daily OHLCV, settlement price, and open interest for options contracts."""
    extra = {"exchange": exchange} if exchange is not None else None
    return query_daily_partitioned(
        ctx, "opt_daily", "opt_daily", OPT_DAILY_COLS,
        ts_code, trade_date, start_date, end_date, fields,
        extra_filters=extra,
        data_dir_override=ctx.data_dir / "options",
        limit=limit,
        offset=offset,
    )
