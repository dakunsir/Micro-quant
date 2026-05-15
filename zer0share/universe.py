from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd

from zer0share.storage import write_universe


INDEX_UNIVERSES = {
    "univ_trade_hs300": "399300.SZ",
    "univ_trade_zz500": "000905.SH",
    "univ_trade_zz1000": "000852.SH",
}


def build_universes(data_dir: str | Path, trade_date: date) -> dict[str, int]:
    data_path = Path(data_dir)
    detail = build_universe_detail(data_path, trade_date)
    outputs = {
        "univ_research_base": detail.loc[detail["in_research_base"], ["trade_date", "ts_code"]],
        "univ_trade_base": detail.loc[detail["in_trade_base"], ["trade_date", "ts_code"]],
    }

    for universe_name, index_code in INDEX_UNIVERSES.items():
        members = _latest_index_members(data_path, index_code, trade_date)
        mask = detail["in_trade_base"] & detail["ts_code"].isin(members)
        outputs[universe_name] = detail.loc[mask, ["trade_date", "ts_code"]]

    counts = {}
    for name, df in outputs.items():
        result = df.assign(universe=name).loc[:, ["trade_date", "universe", "ts_code"]]
        write_universe(data_path, name, trade_date, result)
        counts[name] = len(result)
    return counts


def build_universe_detail(data_dir: str | Path, trade_date: date) -> pd.DataFrame:
    data_path = Path(data_dir)
    basic = _read_basic(data_path)
    daily_today = _read_daily_table(data_path, "daily_kline", trade_date)
    daily_basic = _read_daily_table(data_path, "daily_basic", trade_date)
    stock_st = _read_daily_table(data_path, "stock_st", trade_date)
    suspend_d = _read_daily_table(data_path, "suspend_d", trade_date)
    stk_limit = _read_daily_table(data_path, "stk_limit", trade_date)
    avg_amount = _rolling_avg_amount_20d(data_path, trade_date)

    df = basic.merge(daily_today, on="ts_code", how="left", suffixes=("", "_daily"))
    df = df.merge(daily_basic[["ts_code", "total_mv"]], on="ts_code", how="left")
    df = df.merge(avg_amount, on="ts_code", how="left")
    df = df.merge(stk_limit[["ts_code", "up_limit", "down_limit"]], on="ts_code", how="left")

    df["trade_date"] = trade_date
    trade_ts = pd.Timestamp(trade_date)
    df["is_a_share_common"] = _is_a_share_common(df)
    list_date = pd.to_datetime(df["list_date"], errors="coerce")
    delist_date = pd.to_datetime(df["delist_date"], errors="coerce")
    df["is_listed"] = list_date <= trade_ts
    df["is_not_delisted"] = delist_date.isna() | (delist_date > trade_ts)
    df["is_old_enough"] = list_date <= trade_ts - pd.Timedelta(days=183)
    df["is_st"] = df["ts_code"].isin(set(stock_st["ts_code"]))
    df["is_suspended"] = df["ts_code"].isin(set(suspend_d["ts_code"]))
    df["has_amount_liquidity"] = df["avg_amount_20d"] >= 10000
    df["passes_research_mv"] = _not_bottom_market_cap(df, 0.02)
    df["passes_trade_mv"] = _not_bottom_market_cap(df, 0.05)
    df["is_one_price_up_limit"] = _is_one_price_limit(df, "up_limit")
    df["is_one_price_down_limit"] = _is_one_price_limit(df, "down_limit")

    df["in_research_base"] = (
        df["is_a_share_common"]
        & df["is_listed"]
        & df["is_not_delisted"]
        & ~df["is_st"]
        & df["is_old_enough"]
        & df["has_amount_liquidity"]
        & df["passes_research_mv"]
    )
    df["in_trade_base"] = (
        df["in_research_base"]
        & ~df["is_suspended"]
        & ~df["is_one_price_up_limit"]
        & ~df["is_one_price_down_limit"]
        & df["passes_trade_mv"]
    )
    return df


def _read_basic(data_dir: Path) -> pd.DataFrame:
    path = data_dir / "basic" / "data.parquet"
    if not path.exists():
        raise FileNotFoundError("basic data not found; run `python main.py sync --table basic` first")
    return pd.read_parquet(path)


def _read_daily_table(data_dir: Path, table_name: str, trade_date: date) -> pd.DataFrame:
    path = data_dir / table_name / f"date={trade_date.strftime('%Y%m%d')}" / "data.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"{table_name} data not found for {trade_date}; "
            f"run `python main.py sync --table {table_name} --start-date {trade_date} --end-date {trade_date}` first"
        )
    return pd.read_parquet(path)


def _rolling_avg_amount_20d(data_dir: Path, trade_date: date) -> pd.DataFrame:
    table_dir = data_dir / "daily_kline"
    if not table_dir.exists():
        raise FileNotFoundError("daily_kline data not found; run `python main.py sync --table daily_kline` first")

    start = trade_date - timedelta(days=90)
    pattern = table_dir / "date=*" / "data.parquet"
    sql = """
        SELECT ts_code, trade_date, amount
        FROM read_parquet(?, hive_partitioning=true)
        WHERE trade_date >= ? AND trade_date <= ?
        ORDER BY ts_code, trade_date
    """
    daily = duckdb.connect().execute(sql, [str(pattern), start, trade_date]).fetchdf()
    if daily.empty:
        return pd.DataFrame(columns=["ts_code", "avg_amount_20d"])
    tail = daily.groupby("ts_code", group_keys=False).tail(20)
    stats = tail.groupby("ts_code").agg(avg_amount_20d=("amount", "mean"), obs=("amount", "count"))
    stats = stats.loc[stats["obs"] >= 20, ["avg_amount_20d"]].reset_index()
    return stats


def _latest_index_members(data_dir: Path, index_code: str, trade_date: date) -> set[str]:
    table_dir = data_dir / "index_weight"
    if not table_dir.exists():
        raise FileNotFoundError("index_weight data not found; run `python main.py sync --table index_weight` first")
    pattern = table_dir / "index_code=*" / "date=*" / "data.parquet"
    sql = """
        SELECT con_code, trade_date
        FROM read_parquet(?, hive_partitioning=true)
        WHERE index_code = ? AND trade_date <= ?
        QUALIFY trade_date = max(trade_date) OVER ()
    """
    df = duckdb.connect().execute(sql, [str(pattern), index_code, trade_date]).fetchdf()
    return set(df["con_code"]) if not df.empty else set()


def _is_a_share_common(df: pd.DataFrame) -> pd.Series:
    symbol = df["symbol"].astype(str)
    ts_code = df["ts_code"].astype(str)
    is_a_suffix = ts_code.str.endswith((".SH", ".SZ", ".BJ"))
    is_b_share = symbol.str.startswith(("200", "900"))
    is_cdr = df["market"].astype(str).str.upper().eq("CDR")
    return is_a_suffix & ~is_b_share & ~is_cdr


def _not_bottom_market_cap(df: pd.DataFrame, pct: float) -> pd.Series:
    valid = df["total_mv"].notna()
    result = pd.Series(False, index=df.index)
    if not valid.any():
        return result
    ranks = df.loc[valid, "total_mv"].rank(method="first", ascending=True)
    cutoff = int(len(ranks) * pct)
    result.loc[valid] = ranks > cutoff
    return result


def _is_one_price_limit(df: pd.DataFrame, limit_column: str) -> pd.Series:
    price_cols = ["open", "high", "low", "close"]
    same_price = df[price_cols].nunique(axis=1, dropna=False) == 1
    at_limit = (df["close"] - df[limit_column]).abs() < 0.01
    return same_price & at_limit
