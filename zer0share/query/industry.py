import duckdb
import pandas as pd

from zer0share.query import QueryContext
from zer0share.query._helpers import parse_fields
from zer0share.schema import SW_CLASSIFY_COLS, SW_MEMBER_COLS, CI_MEMBER_COLS


def index_classify(ctx: QueryContext, level=None, src=None, fields=None,
                   limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query Shenwan (SW) industry classification hierarchy (L1/L2/L3 levels)."""
    path = ctx.data_dir / "industry" / "sw_classify" / "data.parquet"
    if not path.exists():
        raise FileNotFoundError(
            "sw_classify data not found; run `python main.py sync --table industry` first"
        )
    selected = parse_fields(fields, SW_CLASSIFY_COLS)
    where = []
    params = []
    if level is not None:
        where.append("level = ?"); params.append(level)
    if src is not None:
        where.append("src = ?"); params.append(src)
    sql = f"SELECT {', '.join(selected)} FROM read_parquet(?)"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY industry_code"
    if limit is not None:
        sql += " LIMIT ?"; params.append(limit)
    if offset is not None:
        sql += " OFFSET ?"; params.append(offset)
    return duckdb.connect().execute(sql, [str(path), *params]).fetchdf()


def index_member_all(ctx: QueryContext, l1_code=None, ts_code=None, is_new=None, fields=None,
                     limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query Shenwan industry membership: which stocks belong to which SW industry."""
    path = ctx.data_dir / "industry" / "sw_member" / "data.parquet"
    if not path.exists():
        raise FileNotFoundError(
            "sw_member data not found; run `python main.py sync --table industry` first"
        )
    selected = parse_fields(fields, SW_MEMBER_COLS)
    where = []
    params = []
    if l1_code is not None:
        where.append("l1_code = ?"); params.append(l1_code)
    if ts_code is not None:
        codes = [c.strip() for c in ts_code.split(",") if c.strip()]
        placeholders = ", ".join("?" for _ in codes)
        where.append(f"ts_code IN ({placeholders})"); params.extend(codes)
    if is_new is not None:
        where.append("is_new = ?"); params.append(is_new)
    sql = f"SELECT {', '.join(selected)} FROM read_parquet(?)"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ts_code, l1_code"
    if limit is not None:
        sql += " LIMIT ?"; params.append(limit)
    if offset is not None:
        sql += " OFFSET ?"; params.append(offset)
    return duckdb.connect().execute(sql, [str(path), *params]).fetchdf()


def ci_index_member(ctx: QueryContext, l1_code=None, ts_code=None, is_new=None, fields=None,
                    limit: int | None = None, offset: int | None = None) -> pd.DataFrame:
    """Query China Securities Index (CI) industry membership."""
    path = ctx.data_dir / "industry" / "ci_member" / "data.parquet"
    if not path.exists():
        raise FileNotFoundError(
            "ci_member data not found; run `python main.py sync --table ci_member` first"
        )
    selected = parse_fields(fields, CI_MEMBER_COLS)
    where = []
    params = []
    if l1_code is not None:
        where.append("l1_code = ?"); params.append(l1_code)
    if ts_code is not None:
        codes = [c.strip() for c in ts_code.split(",") if c.strip()]
        placeholders = ", ".join("?" for _ in codes)
        where.append(f"ts_code IN ({placeholders})"); params.extend(codes)
    if is_new is not None:
        where.append("is_new = ?"); params.append(is_new)
    sql = f"SELECT {', '.join(selected)} FROM read_parquet(?)"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ts_code, l1_code"
    if limit is not None:
        sql += " LIMIT ?"; params.append(limit)
    if offset is not None:
        sql += " OFFSET ?"; params.append(offset)
    return duckdb.connect().execute(sql, [str(path), *params]).fetchdf()
