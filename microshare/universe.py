import datetime as dt
import json
from bisect import bisect_left, bisect_right
from pathlib import Path

import duckdb
import pandas as pd
from loguru import logger

from microshare.config import UniverseConfig
from microshare.storage import read_trade_cal, write_universe


FIRST_UNIVERSE_DATE = dt.date(2016, 1, 1)
PROGRESS_INTERVAL = 50
BASE_UNIVERSES = ("univ_research_base", "univ_trade_base")
DERIVED_TRADE_UNIVERSES = ("univ_trade_smallcap",)
INDEX_UNIVERSES = {
    "univ_trade_hs300": "399300.SZ",
    "univ_trade_zz500": "000905.SH",
    "univ_trade_zz1000": "000852.SH",
}
UNIVERSE_NAMES = (*BASE_UNIVERSES, *INDEX_UNIVERSES.keys(), *DERIVED_TRADE_UNIVERSES)
MAINBOARD_MICROCAP_DEFAULT_NAME = "hushen_mainboard_previous_day_bottom1000"
MAINBOARD_MICROCAP_DEFAULT_PREFIXES = [
    "600", "601", "603", "605", "000", "001", "002", "003"
]


def build_universes_range(
    data_dir: str | Path,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
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


def build_universes(data_dir: str | Path, trade_date: dt.date) -> dict[str, int]:
    data_path = Path(data_dir)
    detail = build_universe_detail(data_path, trade_date)
    outputs = {
        "univ_research_base": detail.loc[detail["in_research_base"], ["trade_date", "ts_code"]],
        "univ_trade_base": detail.loc[detail["in_trade_base"], ["trade_date", "ts_code"]],
    }
    trade_base = detail.loc[detail["in_trade_base"]]
    smallcap_mask = detail.index.isin(_bottom_market_cap(trade_base, 0.20).index)
    outputs["univ_trade_smallcap"] = detail.loc[
        smallcap_mask, ["trade_date", "ts_code"]
    ]

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


def _open_trading_days(data_dir: Path, start: dt.date, end: dt.date) -> list[dt.date]:
    trade_cal = read_trade_cal(data_dir, "SSE")
    if trade_cal.empty:
        raise FileNotFoundError(
            "SSE trade_cal data not found; run `python main.py sync --table trade_cal` first"
        )
    cal_dates = pd.to_datetime(trade_cal["cal_date"], format="%Y%m%d").dt.date
    mask = (
        (cal_dates >= start)
        & (cal_dates <= end)
        & (trade_cal["is_open"] == True)
    )
    return sorted(cal_dates[mask].tolist())


def _universe_partitions_exist(data_dir: Path, trade_date: dt.date) -> bool:
    date_part = f"date={trade_date.strftime('%Y%m%d')}"
    return all(
        (data_dir / "stock" / "universe" / f"name={name}" / date_part / "data.parquet").exists()
        for name in UNIVERSE_NAMES
    )


def _latest_complete_source_date(data_dir: Path) -> dt.date:
    required_tables = ("daily_kline", "daily_basic", "stock_st", "suspend_d", "stk_limit")
    available_dates = [_partition_dates(data_dir / "stock" / table_name) for table_name in required_tables]
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


def _default_range_start(data_dir: Path, end: dt.date, incremental: bool) -> dt.date:
    if not incremental:
        return FIRST_UNIVERSE_DATE
    latest_universe_date = _latest_complete_universe_date(data_dir)
    if latest_universe_date is None:
        return FIRST_UNIVERSE_DATE

    next_days = _open_trading_days(
        data_dir, latest_universe_date + dt.timedelta(days=1), end
    )
    return next_days[0] if next_days else end + dt.timedelta(days=1)


def _latest_complete_universe_date(data_dir: Path) -> dt.date | None:
    available_dates = [
        _partition_dates(data_dir / "stock" / "universe" / f"name={name}")
        for name in UNIVERSE_NAMES
    ]
    if any(not dates for dates in available_dates):
        return None
    common_dates = set.intersection(*available_dates)
    return max(common_dates) if common_dates else None


def _partition_dates(table_dir: Path) -> set[dt.date]:
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
    trade_date: dt.date,
    built_days: int,
    skipped_days: int,
) -> None:
    percent = processed / total * 100
    logger.info(
        f"build_universe 同步进度: {processed}/{total} ({percent:.1f}%), "
        f"当前日期 {trade_date}, 构建 {built_days} 天, 跳过已存在 {skipped_days} 天"
    )


def build_universe_detail(data_dir: str | Path, trade_date: dt.date) -> pd.DataFrame:
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
    path = data_dir / "stock" / "basic" / "data.parquet"
    if not path.exists():
        raise FileNotFoundError("basic data not found; run `python main.py sync --table basic` first")
    return pd.read_parquet(path)


def _read_daily_table(data_dir: Path, table_name: str, trade_date: dt.date) -> pd.DataFrame:
    path = data_dir / "stock" / table_name / f"date={trade_date.strftime('%Y%m%d')}" / "data.parquet"
    if not path.exists():
        date_value = trade_date.strftime("%Y%m%d")
        raise FileNotFoundError(
            f"{table_name} data not found for {date_value}; "
            f"run `python main.py sync --table {table_name} --start-date {date_value} --end-date {date_value}` first"
        )
    return pd.read_parquet(path)


def _rolling_avg_amount_20d(data_dir: Path, trade_date: dt.date) -> pd.DataFrame:
    table_dir = data_dir / "stock" / "daily_kline"
    if not table_dir.exists():
        raise FileNotFoundError("daily_kline data not found; run `python main.py sync --table daily_kline` first")

    start = trade_date - dt.timedelta(days=90)
    pattern = table_dir / "date=*" / "data.parquet"
    sql = """
        SELECT ts_code, trade_date, amount
        FROM read_parquet(?, hive_partitioning=true)
        WHERE replace(CAST(trade_date AS VARCHAR), '-', '') >= ?
          AND replace(CAST(trade_date AS VARCHAR), '-', '') <= ?
        ORDER BY ts_code, trade_date
    """
    daily = duckdb.connect().execute(
        sql, [str(pattern), start.strftime("%Y%m%d"), trade_date.strftime("%Y%m%d")]
    ).fetchdf()
    if daily.empty:
        return pd.DataFrame(columns=["ts_code", "avg_amount_20d"])
    tail = daily.groupby("ts_code", group_keys=False).tail(20)
    stats = tail.groupby("ts_code").agg(avg_amount_20d=("amount", "mean"), obs=("amount", "count"))
    stats = stats.loc[stats["obs"] >= 20, ["avg_amount_20d"]].reset_index()
    return stats


def _latest_index_members(data_dir: Path, index_code: str, trade_date: dt.date) -> set[str]:
    table_dir = data_dir / "index" / "index_weight"
    if not table_dir.exists():
        raise FileNotFoundError("index_weight data not found; run `python main.py sync --table index_weight` first")
    pattern = table_dir / "index_code=*" / "date=*" / "data.parquet"
    sql = """
        SELECT con_code, trade_date
        FROM read_parquet(?, hive_partitioning=true)
        WHERE index_code = ?
          AND replace(CAST(trade_date AS VARCHAR), '-', '') <= ?
        QUALIFY trade_date = max(trade_date) OVER ()
    """
    df = duckdb.connect().execute(
        sql, [str(pattern), index_code, trade_date.strftime("%Y%m%d")]
    ).fetchdf()
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


def _bottom_market_cap(df: pd.DataFrame, pct: float) -> pd.DataFrame:
    valid = df["total_mv"].notna()
    if not valid.any():
        return df.iloc[0:0]
    ranks = df.loc[valid, "total_mv"].rank(method="first", ascending=True)
    cutoff = int(len(ranks) * pct)
    return df.loc[ranks[ranks <= cutoff].index]


def _is_one_price_limit(df: pd.DataFrame, limit_column: str) -> pd.Series:
    price_cols = ["open", "high", "low", "close"]
    same_price = df[price_cols].nunique(axis=1, dropna=False) == 1
    at_limit = (df["close"] - df[limit_column]).abs() < 0.01
    return same_price & at_limit


def _default_mainboard_microcap_config() -> UniverseConfig:
    return UniverseConfig(
        name=MAINBOARD_MICROCAP_DEFAULT_NAME,
        version="current",
        target_count=1000,
        min_listing_sessions=120,
        exclude_st=True,
        main_board_prefixes=list(MAINBOARD_MICROCAP_DEFAULT_PREFIXES),
    )


def _microcap_config_payload(config: UniverseConfig) -> dict[str, object]:
    return {
        "name": config.name,
        "version": config.version,
        "target_count": config.target_count,
        "min_listing_sessions": config.min_listing_sessions,
        "exclude_st": config.exclude_st,
        "main_board_prefixes": list(config.main_board_prefixes),
    }


def _parse_date_series(values: pd.Series) -> pd.Series:
    text = values.astype(str)
    parsed = pd.to_datetime(text, format="%Y%m%d", errors="coerce")
    missing = parsed.isna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(text.loc[missing], errors="coerce")
    return parsed.map(lambda value: value.date() if pd.notna(value) else None)


def _load_sse_calendar(data_dir: Path) -> tuple[list[dt.date], dict[dt.date, dt.date]]:
    trade_cal = read_trade_cal(data_dir, "SSE")
    if trade_cal.empty:
        raise FileNotFoundError(
            "SSE trade_cal data not found; run `python main.py sync --table trade_cal` first"
        )
    required = {"cal_date", "is_open"}
    missing = required - set(trade_cal.columns)
    if missing:
        raise ValueError(f"trade_cal is missing columns: {', '.join(sorted(missing))}")

    frame = trade_cal.copy()
    frame["_cal_date"] = _parse_date_series(frame["cal_date"])
    frame = frame.dropna(subset=["_cal_date"])
    frame["_is_open"] = frame["is_open"].astype(bool)
    open_dates = sorted(set(frame.loc[frame["_is_open"], "_cal_date"]))

    pretrade: dict[dt.date, dt.date] = {}
    if "pretrade_date" in frame.columns:
        for cal_date, pretrade_date in zip(
            frame["_cal_date"], _parse_date_series(frame["pretrade_date"])
        ):
            if pd.notna(pretrade_date):
                pretrade[cal_date] = pretrade_date
    return open_dates, pretrade


def _mainboard_trade_day_pairs(
    data_dir: Path, start_date: dt.date, end_date: dt.date
) -> list[tuple[dt.date, dt.date]]:
    open_dates, pretrade = _load_sse_calendar(data_dir)
    open_set = set(open_dates)
    pairs: list[tuple[dt.date, dt.date]] = []
    for effective_date in open_dates:
        if effective_date < start_date or effective_date > end_date:
            continue
        source_date = pretrade.get(effective_date)
        if source_date not in open_set:
            position = bisect_left(open_dates, effective_date) - 1
            source_date = open_dates[position] if position >= 0 else None
        if source_date is None or source_date >= effective_date:
            raise ValueError(
                f"无法为生效日 {effective_date} 找到严格更早的前一交易日"
            )
        pairs.append((effective_date, source_date))
    return pairs


def _latest_microcap_source_date(data_dir: Path) -> dt.date:
    required_tables = ("daily_basic", "stock_st")
    available_dates = [
        _partition_dates(data_dir / "stock" / table_name)
        for table_name in required_tables
    ]
    missing = [
        table_name
        for table_name, dates in zip(required_tables, available_dates)
        if not dates
    ]
    if missing:
        raise FileNotFoundError(
            f"required data not found for {', '.join(missing)}; "
            "run `python main.py sync --table daily_basic --start-date 20151231` "
            "and `python main.py sync --table stock_st --start-date 20151231` first"
        )
    common_dates = set.intersection(*available_dates)
    if not common_dates:
        raise FileNotFoundError(
            "daily_basic and stock_st have no common source date; "
            "synchronize both tables for the same date range first"
        )
    return max(common_dates)


def _microcap_partition_dir(data_dir: Path, config: UniverseConfig, effective_date: dt.date) -> Path:
    return (
        data_dir
        / "stock"
        / "universe"
        / f"name={config.name}"
        / f"date={effective_date.strftime('%Y%m%d')}"
    )


def _microcap_manifest_path(
    data_dir: Path, config: UniverseConfig, effective_date: dt.date
) -> Path:
    return _microcap_partition_dir(data_dir, config, effective_date) / "manifest.json"


def _read_microcap_manifest(path: Path) -> dict[str, object]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"股票池 manifest 无法读取: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"股票池 manifest 必须是对象: {path}")
    return value


def _assert_microcap_manifest_compatible(
    data_dir: Path,
    config: UniverseConfig,
    effective_date: dt.date,
    source_date: dt.date,
) -> dict[str, object]:
    partition_dir = _microcap_partition_dir(data_dir, config, effective_date)
    data_path = partition_dir / "data.parquet"
    manifest_path = partition_dir / "manifest.json"
    if not data_path.exists() or not manifest_path.exists():
        raise ValueError(
            f"股票池分区不完整: {partition_dir}；请删除该分区后显式重建"
        )
    manifest = _read_microcap_manifest(manifest_path)
    if manifest.get("config") != _microcap_config_payload(config):
        raise ValueError(
            f"股票池配置版本或规则不一致: {partition_dir}；请显式重建"
        )
    if (
        manifest.get("effective_trade_date") != effective_date.strftime("%Y%m%d")
        or manifest.get("source_trade_date") != source_date.strftime("%Y%m%d")
    ):
        raise ValueError(
            f"股票池点时日期不一致: {partition_dir}；请显式重建"
        )
    return manifest


def _listing_session_count(
    list_date: object, source_date: dt.date, open_dates: list[dt.date]
) -> int:
    if pd.isna(list_date):
        return 0
    parsed = list_date if isinstance(list_date, dt.date) else pd.Timestamp(list_date).date()
    start = bisect_left(open_dates, parsed)
    end = bisect_right(open_dates, source_date)
    return max(0, end - start)


def _select_mainboard_microcap(
    data_dir: Path,
    effective_date: dt.date,
    source_date: dt.date,
    config: UniverseConfig,
) -> tuple[pd.DataFrame, dict[str, object]]:
    basic = _read_basic(data_dir).copy()
    required_basic = {"ts_code", "list_date", "delist_date"}
    missing_basic = required_basic - set(basic.columns)
    if missing_basic:
        raise ValueError(
            f"basic data is missing columns: {', '.join(sorted(missing_basic))}"
        )

    daily_basic = _read_daily_table(data_dir, "daily_basic", source_date).copy()
    if "ts_code" not in daily_basic.columns or "total_mv" not in daily_basic.columns:
        raise ValueError("daily_basic data must contain ts_code and total_mv")
    daily_basic = daily_basic[["ts_code", "total_mv"]].copy()
    daily_basic["ts_code"] = daily_basic["ts_code"].astype(str)
    daily_basic["total_mv"] = pd.to_numeric(daily_basic["total_mv"], errors="coerce")
    daily_basic = (
        daily_basic.sort_values(["ts_code", "total_mv"], na_position="last")
        .drop_duplicates("ts_code", keep="first")
    )

    stock_st = _read_daily_table(data_dir, "stock_st", source_date)
    st_codes = (
        set(stock_st["ts_code"].dropna().astype(str))
        if "ts_code" in stock_st.columns
        else set()
    )
    open_dates, _ = _load_sse_calendar(data_dir)

    basic["ts_code"] = basic["ts_code"].astype(str)
    frame = basic.merge(daily_basic, on="ts_code", how="left")
    code_prefix = frame["ts_code"].str.split(".", n=1).str[0]
    list_dates = _parse_date_series(frame["list_date"])
    delist_dates = _parse_date_series(frame["delist_date"])
    frame["listing_sessions"] = [
        _listing_session_count(value, source_date, open_dates)
        for value in list_dates
    ]
    frame["is_st"] = frame["ts_code"].isin(st_codes)
    frame["total_mv"] = pd.to_numeric(frame["total_mv"], errors="coerce")
    frame["is_mainboard"] = code_prefix.str.startswith(tuple(config.main_board_prefixes))
    frame["is_listed"] = list_dates.notna() & (list_dates <= source_date)
    frame["is_not_delisted"] = delist_dates.isna() | (delist_dates > source_date)
    frame["has_listing_age"] = frame["listing_sessions"] >= config.min_listing_sessions
    frame["has_valid_mv"] = frame["total_mv"].notna() & (frame["total_mv"] > 0)

    eligible = frame[
        frame["is_mainboard"]
        & frame["is_listed"]
        & frame["is_not_delisted"]
        & frame["has_listing_age"]
        & frame["has_valid_mv"]
        & (~frame["is_st"] if config.exclude_st else True)
    ].copy()
    eligible = eligible.sort_values(
        ["total_mv", "ts_code"], ascending=[True, True], kind="mergesort"
    )
    members = eligible.head(config.target_count)[["ts_code"]].copy()
    members.insert(0, "universe", config.name)
    members.insert(0, "trade_date", effective_date.strftime("%Y%m%d"))

    warnings: list[str] = []
    if len(eligible) < config.target_count:
        warnings.append(
            f"合格股票仅 {len(eligible)} 只，低于目标 {config.target_count} 只"
        )
    manifest = {
        "schema_version": 1,
        "universe": config.name,
        "version": config.version,
        "config": _microcap_config_payload(config),
        "effective_trade_date": effective_date.strftime("%Y%m%d"),
        "source_trade_date": source_date.strftime("%Y%m%d"),
        "member_count": len(members),
        "eligible_count": len(eligible),
        "quality_status": "WARNING" if warnings else "OK",
        "warnings": warnings,
    }
    return members, manifest


def build_mainboard_microcap(
    data_dir: str | Path,
    trade_date: dt.date,
    config: UniverseConfig | None = None,
) -> dict[str, object]:
    """Build one point-in-time main-board bottom-market-cap universe."""
    data_path = Path(data_dir)
    config = config or _default_mainboard_microcap_config()
    if trade_date < FIRST_UNIVERSE_DATE:
        raise ValueError(f"trade_date must be on or after {FIRST_UNIVERSE_DATE}")
    pairs = _mainboard_trade_day_pairs(data_path, trade_date, trade_date)
    if not pairs:
        raise ValueError(f"trade_date {trade_date} is not an SSE trading day")
    effective_date, source_date = pairs[0]
    partition_dir = _microcap_partition_dir(data_path, config, effective_date)
    data_path_out = partition_dir / "data.parquet"
    if data_path_out.exists():
        _assert_microcap_manifest_compatible(
            data_path, config, effective_date, source_date
        )

    members, manifest = _select_mainboard_microcap(
        data_path, effective_date, source_date, config
    )
    write_universe(data_path, config.name, effective_date, members)
    partition_dir.mkdir(parents=True, exist_ok=True)
    with _microcap_manifest_path(data_path, config, effective_date).open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    logger.info(
        f"{config.name} 单日完成: effective={effective_date}, "
        f"source={source_date}, members={manifest['member_count']}"
    )
    return manifest


def build_mainboard_microcap_range(
    data_dir: str | Path,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
    config: UniverseConfig | None = None,
    incremental: bool = True,
) -> dict[str, object]:
    """Build point-in-time snapshots for a range of trading days."""
    data_path = Path(data_dir)
    config = config or _default_mainboard_microcap_config()
    end = end_date or _latest_microcap_source_date(data_path)
    start = start_date or FIRST_UNIVERSE_DATE
    if start < FIRST_UNIVERSE_DATE:
        raise ValueError(f"start_date must be on or after {FIRST_UNIVERSE_DATE}")
    if start > end:
        if start_date is not None or end_date is not None:
            raise ValueError("start_date must be on or before end_date")
        return {
            "start_date": start,
            "end_date": end,
            "trading_days": 0,
            "built_days": 0,
            "skipped_days": 0,
            "member_count": 0,
            "counts": {config.name: 0},
            "warnings": [],
        }

    pairs = _mainboard_trade_day_pairs(data_path, start, end)
    built_days = 0
    skipped_days = 0
    member_count = 0
    warnings: list[str] = []
    for effective_date, source_date in pairs:
        partition_dir = _microcap_partition_dir(data_path, config, effective_date)
        data_file = partition_dir / "data.parquet"
        if incremental and data_file.exists():
            existing = _assert_microcap_manifest_compatible(
                data_path, config, effective_date, source_date
            )
            skipped_days += 1
            member_count += int(existing.get("member_count", 0))
            warnings.extend(str(item) for item in existing.get("warnings", []))
            continue
        manifest = build_mainboard_microcap(data_path, effective_date, config)
        built_days += 1
        member_count += int(manifest["member_count"])
        warnings.extend(str(item) for item in manifest["warnings"])

    logger.info(
        f"{config.name} 区间完成: {start} ~ {end}, "
        f"构建 {built_days} 天, 跳过 {skipped_days} 天"
    )
    return {
        "start_date": start,
        "end_date": end,
        "trading_days": len(pairs),
        "built_days": built_days,
        "skipped_days": skipped_days,
        "member_count": member_count,
        "counts": {config.name: member_count},
        "warnings": warnings,
    }
