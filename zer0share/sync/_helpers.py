import time
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

from loguru import logger

from zer0share.storage import daily_partition_exists, write_daily_partition
from zer0share.sync import SyncContext


FIRST_DATE = date(2016, 1, 1)
TRADE_CAL_FIRST_DATE = date(1990, 1, 1)
PROGRESS_INTERVAL = 50
EXCHANGES = ["SSE", "SZSE"]
INDEX_CODES = ["399300.SZ", "000905.SH", "000852.SH"]
ALL_EXCHANGES = ["SSE", "SZSE", "CFFEX", "DCE", "SHFE", "CZCE", "INE", "GFEX"]


def parse_tushare_date(value) -> date:
    import datetime as dt
    if isinstance(value, dt.date):
        return value
    import pandas as pd
    return pd.to_datetime(value, format="%Y%m%d").date()


def should_log_progress(processed: int, total: int) -> bool:
    return processed == total or processed % PROGRESS_INTERVAL == 0


def log_daily_progress(
    table_name: str,
    processed: int,
    total: int,
    trade_date: date,
    success: int,
    empty: int,
    skipped_existing: int,
) -> None:
    percent = processed / total * 100
    logger.info(
        f"{table_name} 同步进度: {processed}/{total} ({percent:.1f}%), "
        f"当前日期 {trade_date}, "
        f"成功 {success} 天, 空数据 {empty} 天, 跳过已存在 {skipped_existing} 天"
    )


def month_ranges(start: date, end: date) -> list[tuple[date, date]]:
    ranges = []
    current = date(start.year, start.month, 1)
    while current <= end:
        next_month = (
            date(current.year + 1, 1, 1)
            if current.month == 12
            else date(current.year, current.month + 1, 1)
        )
        month_start = max(start, current)
        month_end = min(end, next_month - timedelta(days=1))
        ranges.append((month_start, month_end))
        current = next_month
    return ranges


def week_ranges(start: date, end: date) -> list[tuple[str, date]]:
    weeks = []
    seen: set = set()
    current = start
    while current <= end:
        iso_year, iso_week, _ = current.isocalendar()
        week_key = (iso_year, iso_week)
        if week_key not in seen:
            seen.add(week_key)
            week_num = f"{iso_year}{iso_week:02d}"
            monday = current - timedelta(days=current.weekday())
            weeks.append((week_num, monday))
        current += timedelta(days=7)
    return weeks


def index_weight_meta_key(index_code: str) -> str:
    return f"index_weight:{index_code}"


def ensure_trade_cal_loaded(ctx: SyncContext) -> None:
    from zer0share.sync import calendar as cal_module
    if ctx.meta.get_last_date("trade_cal") is None:
        cal_module.sync_trade_cal(ctx)


def skip_if_not_trading(ctx: SyncContext, exchange: str) -> bool:
    ensure_trade_cal_loaded(ctx)
    today = date.today()
    if not ctx.meta.is_trading_day(exchange, today):
        logger.info(f"今日 {today} 非交易日，跳过同步")
        return True
    return False


def sync_daily_partitioned(
    ctx: SyncContext,
    table_name: str,
    fetch: Callable,
    start_date: date | None,
    end_date: date | None,
    write_empty: bool = False,
    data_dir: Path | None = None,
    exchange: str = "SSE",
) -> None:
    base_dir = data_dir or ctx.cfg.data_dir
    today = date.today()
    last = ctx.meta.get_last_date(table_name)
    if start_date is None:
        start = (last + timedelta(days=1)) if last else FIRST_DATE
        end = today
    else:
        start = start_date
        end = end_date or today

    if start_date is None and start > end:
        logger.info(f"{table_name} 已是最新，无需同步")
        return
    if start > end:
        raise ValueError("start_date must be on or before end_date")

    trading_days = ctx.meta.get_trading_days(exchange, start, end)
    if not trading_days and ctx.meta.get_last_date("trade_cal") is None:
        raise RuntimeError(
            f"DuckDB 中无 {exchange} trade_cal 数据，请先运行 "
            "python main.py sync --table trade_cal"
        )
    if not trading_days:
        logger.info("指定范围内无交易日，无需同步")
        return

    success = 0
    empty = 0
    skipped_existing = 0
    frontier = last
    logger.info(
        f"{table_name} 同步开始: {start} ~ {end}, 共 {len(trading_days)} 个交易日"
    )
    for processed, trade_date in enumerate(trading_days, start=1):
        if daily_partition_exists(base_dir, table_name, trade_date):
            skipped_existing += 1
            if should_log_progress(processed, len(trading_days)):
                log_daily_progress(
                    table_name, processed, len(trading_days), trade_date,
                    success, empty, skipped_existing,
                )
            continue
        try:
            df = fetch(trade_date)
            time.sleep(0.2)
            if not df.empty or write_empty:
                write_daily_partition(base_dir, table_name, trade_date, df)
                if frontier is None or trade_date > frontier:
                    ctx.meta.update_last_date(table_name, trade_date)
                    frontier = trade_date
                if df.empty:
                    empty += 1
                else:
                    success += 1
            else:
                empty += 1
        except Exception as e:
            logger.error(f"{table_name} {trade_date} 同步失败: {e}")
            ctx.notifier.send(f"{table_name} {trade_date} 同步失败: {e}")
            raise
        if should_log_progress(processed, len(trading_days)):
            log_daily_progress(
                table_name, processed, len(trading_days), trade_date,
                success, empty, skipped_existing,
            )

    msg = (
        f"{table_name} 同步完成: 成功 {success} 天, "
        f"空数据 {empty} 天, 跳过已存在 {skipped_existing} 天, "
        f"共 {len(trading_days)} 个交易日"
    )
    logger.info(msg)
    ctx.notifier.send(msg)
