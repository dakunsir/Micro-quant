import duckdb
import pandas as pd

from zer0share.query import QueryContext
from zer0share.query._helpers import parse_fields, parse_is_open
from zer0share.schema import TRADE_CAL_COLS


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
    trade_cal_dir = ctx.data_dir / "trade_cal"
    if not trade_cal_dir.exists():
        raise FileNotFoundError(
            "trade_cal data not found; run `python main.py sync --table trade_cal` first"
        )

    columns = parse_fields(fields, TRADE_CAL_COLS)
    where = ["exchange = ?"]
    params = [exchange]
    if start_date is not None and end_date is not None and end_date < start_date:
        raise ValueError("end_date must be on or after start_date")
    if start_date is not None:
        where.append("cal_date >= ?")
        params.append(start_date)
    if end_date is not None:
        where.append("cal_date <= ?")
        params.append(end_date)
    if is_open is not None:
        where.append("is_open = ?")
        params.append(parse_is_open(is_open))

    pattern = trade_cal_dir / "exchange=*" / "data.parquet"
    sql = (
        f"SELECT {', '.join(columns)} FROM read_parquet(?, hive_partitioning=true) "
        f"WHERE {' AND '.join(where)} ORDER BY exchange, cal_date"
    )
    if limit is not None:
        sql += " LIMIT ?"; params.append(limit)
    if offset is not None:
        sql += " OFFSET ?"; params.append(offset)
    return duckdb.connect().execute(sql, [str(pattern), *params]).fetchdf()
