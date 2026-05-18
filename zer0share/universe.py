from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd
from loguru import logger

from zer0share.storage import read_trade_cal, write_universe


FIRST_UNIVERSE_DATE = date(2016, 1, 1)
PROGRESS_INTERVAL = 50
BASE_UNIVERSES = ("univ_research_base", "univ_trade_base")
INDEX_UNIVERSES = {
    "univ_trade_hs300": "399300.SZ",
    "univ_trade_zz500": "000905.SH",
    "univ_trade_zz1000": "000852.SH",
}
UNIVERSE_NAMES = (*BASE_UNIVERSES, *INDEX_UNIVERSES.keys())


def build_universes_range(
    data_dir: str | Path,
    start_date: date | None = None,
    end_date: date | None = None,
    incremental: bool = True,
) -> dict[str, object]:
    data_path = Path(data_dir)
    end = end_date or _latest_complete_source_date(data_path)
    start = start_date or _default_range_start(data_path, end, incremental)
    if start > end:
        if start_date is not None:
            raise ValueError("start_date must be on or before end_date")
        logger.info(f"build_universe 已是最新，无需构建，已覆盖到 {end}")
        return {
            "start_date": end,
            "end_date": end,
            "trading_days": 0,
            "built_days": 0,
            "skipped_days": 0,
            "counts": {name: 0 for name in UNIVERSE_NAMES},
        }

    trading_days = _open_trading_days(data_path, start, end)
    counts = {name: 0 for name in UNIVERSE_NAMES}
    built_days = 0
    skipped_days = 0

    logger.info(
        f"build_universe 同步开始: {start} ~ {end}, 共 {len(trading_days)} 个交易日"
    )
    for processed, trade_date in enumerate(trading_days, start=1):
        if incremental and _universe_partitions_exist(data_path, trade_date):
            skipped_days += 1
            if _should_log_progress(processed, len(trading_days)):
                _log_range_progress(
                    processed, len(trading_days), trade_date, built_days, skipped_days
                )
            continue
        day_counts = build_universes(data_path, trade_date)
        for name, count in day_counts.items():
            counts[name] += count
        built_days += 1
        if _should_log_progress(processed, len(trading_days)):
            _log_range_progress(
                processed, len(trading_days), trade_date, built_days, skipped_days
            )

    logger.info(
        f"build_universe 同步完成: 构建 {built_days} 天, "
        f"跳过已存在 {skipped_days} 天, 共 {len(trading_days)} 个交易日"
    )

    return {
        "start_date": start,
        "end_date": end,
        "trading_days": len(trading_days),
        "built_days": built_days,
        "skipped_days": skipped_days,
        "counts": counts,
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
    logger.info(
        "build_universe 单日完成: "
        f"{trade_date}, " + ", ".join(f"{name}={count}" for name, count in counts.items())
    )
    return counts


def _open_trading_days(data_dir: Path, start: date, end: date) -> list[date]:
    trade_cal = read_trade_cal(data_dir, "SSE")
    if trade_cal.empty:
        raise FileNotFoundError(
            "SSE trade_cal data not found; run `python main.py sync --table trade_cal` first"
        )
    mask = (
        (trade_cal["cal_date"] >= start)
        & (trade_cal["cal_date"] <= end)
        & (trade_cal["is_open"] == True)
    )
    return sorted(trade_cal.loc[mask, "cal_date"].tolist())


def _universe_partitions_exist(data_dir: Path, trade_date: date) -> bool:
    date_part = f"date={trade_date.strftime('%Y%m%d')}"
    return all(
        (data_dir / "universe" / f"name={name}" / date_part / "data.parquet").exists()
        for name in UNIVERSE_NAMES
    )


def _latest_complete_source_date(data_dir: Path) -> date:
    required_tables = ("daily_kline", "daily_basic", "stock_st", "suspend_d", "stk_limit")
    available_dates = [_partition_dates(data_dir / table_name) for table_name in required_tables]
    if any(not dates for dates in available_dates):
        missing = [
            table_name
            for table_name, dates in zip(required_tables, available_dates)
            if not dates
        ]
        raise FileNotFoundError(
            f"required data not found for {', '.join(missing)}; "
            "run `python main.py sync --all` first"
        )
    common_dates = set.intersection(*available_dates)
    if not common_dates:
        raise FileNotFoundError(
            "no common date found across required daily tables; "
            "sync daily_kline, daily_basic, stock_st, suspend_d, and stk_limit first"
        )
    return max(common_dates)


def _default_range_start(data_dir: Path, end: date, incremental: bool) -> date:
    if not incremental:
        return FIRST_UNIVERSE_DATE
    latest_universe_date = _latest_complete_universe_date(data_dir)
    if latest_universe_date is None:
        return FIRST_UNIVERSE_DATE

    next_days = _open_trading_days(
        data_dir, latest_universe_date + timedelta(days=1), end
    )
    return next_days[0] if next_days else end + timedelta(days=1)


def _latest_complete_universe_date(data_dir: Path) -> date | None:
    available_dates = [
        _partition_dates(data_dir / "universe" / f"name={name}")
        for name in UNIVERSE_NAMES
    ]
    if any(not dates for dates in available_dates):
        return None
    common_dates = set.intersection(*available_dates)
    return max(common_dates) if common_dates else None


def _partition_dates(table_dir: Path) -> set[date]:
    if not table_dir.exists():
        return set()
    dates = set()
    for path in table_dir.glob("date=*/data.parquet"):
        value = path.parent.name.removeprefix("date=")
        try:
            dates.add(pd.to_datetime(value, format="%Y%m%d").date())
        except ValueError:
            continue
    return dates


def _should_log_progress(processed: int, total: int) -> bool:
    return total > 0 and (processed == total or processed % PROGRESS_INTERVAL == 0)


def _log_range_progress(
    processed: int,
    total: int,
    trade_date: date,
    built_days: int,
    skipped_days: int,
) -> None:
    percent = processed / total * 100
    logger.info(
        f"build_universe 同步进度: {processed}/{total} ({percent:.1f}%), "
        f"当前日期 {trade_date}, 构建 {built_days} 天, 跳过已存在 {skipped_days} 天"
    )


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
