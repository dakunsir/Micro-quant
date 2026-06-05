import time
from datetime import date, timedelta
from loguru import logger

import pandas as pd

from zer0share.storage import daily_partition_exists, write_daily_partition
from zer0share.sync import SyncContext
from zer0share.sync._helpers import (
    FIRST_DATE, parse_tushare_date, skip_if_not_trading, sync_daily_partitioned,
    week_ranges,
)
from zer0share.fetcher import FUTURES_EXCHANGES


def sync_fut_basic(ctx: SyncContext) -> None:
    if skip_if_not_trading(ctx, "SSE"):
        return
    today = date.today()
    futures_dir = ctx.cfg.data_dir / "futures"
    all_frames = []
    try:
        for exchange in FUTURES_EXCHANGES:
            for fut_type in ("1", "2"):
                df = ctx.fetcher.fetch_fut_basic(exchange, fut_type)
                time.sleep(0.2)
                if not df.empty:
                    all_frames.append(df)
        combined = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()
        write_daily_partition(futures_dir, "fut_basic", today, combined)
        ctx.meta.update_last_date("fut_basic", today)
        logger.info(f"fut_basic 同步完成: {len(combined)} 条")
    except Exception as e:
        logger.error(f"fut_basic 同步失败: {e}")
        ctx.notifier.send(f"fut_basic 同步失败: {e}")
        raise


def sync_fut_daily(ctx: SyncContext, start_date: date | None = None, end_date: date | None = None) -> None:
    sync_daily_partitioned(
        ctx, "fut_daily", ctx.fetcher.fetch_fut_daily, start_date, end_date,
        data_dir=ctx.cfg.data_dir / "futures",
    )


def sync_fut_holding(ctx: SyncContext, start_date: date | None = None, end_date: date | None = None) -> None:
    sync_daily_partitioned(
        ctx, "fut_holding", ctx.fetcher.fetch_fut_holding, start_date, end_date,
        data_dir=ctx.cfg.data_dir / "futures",
    )


def sync_fut_wsr(ctx: SyncContext, start_date: date | None = None, end_date: date | None = None) -> None:
    sync_daily_partitioned(
        ctx, "fut_wsr", ctx.fetcher.fetch_fut_wsr, start_date, end_date,
        data_dir=ctx.cfg.data_dir / "futures",
    )


def sync_fut_settle(ctx: SyncContext, start_date: date | None = None, end_date: date | None = None) -> None:
    sync_daily_partitioned(
        ctx, "fut_settle", ctx.fetcher.fetch_fut_settle, start_date, end_date,
        data_dir=ctx.cfg.data_dir / "futures",
    )


def sync_fut_mapping(ctx: SyncContext, start_date: date | None = None, end_date: date | None = None) -> None:
    sync_daily_partitioned(
        ctx, "fut_mapping", ctx.fetcher.fetch_fut_mapping, start_date, end_date,
        data_dir=ctx.cfg.data_dir / "futures",
    )


def sync_ft_limit(ctx: SyncContext, start_date: date | None = None, end_date: date | None = None) -> None:
    sync_daily_partitioned(
        ctx, "ft_limit", ctx.fetcher.fetch_ft_limit, start_date, end_date,
        data_dir=ctx.cfg.data_dir / "futures",
    )


def sync_fut_weekly(ctx: SyncContext, start_date: date | None = None, end_date: date | None = None) -> None:
    sync_daily_partitioned(
        ctx, "fut_weekly", ctx.fetcher.fetch_fut_weekly, start_date, end_date,
        data_dir=ctx.cfg.data_dir / "futures",
    )


def sync_fut_monthly(ctx: SyncContext, start_date: date | None = None, end_date: date | None = None) -> None:
    sync_daily_partitioned(
        ctx, "fut_monthly", ctx.fetcher.fetch_fut_monthly, start_date, end_date,
        data_dir=ctx.cfg.data_dir / "futures",
    )


def sync_fut_index_daily(ctx: SyncContext, start_date: date | None = None, end_date: date | None = None) -> None:
    if skip_if_not_trading(ctx, "SSE"):
        return
    today = date.today()
    last = ctx.meta.get_last_date("fut_index_daily")

    if start_date is None:
        start = (last + timedelta(days=1)) if last else FIRST_DATE
        end = today
    else:
        start = start_date
        end = end_date or today

    if start_date is None and start > end:
        logger.info("fut_index_daily 已是最新，无需同步")
        return
    if start > end:
        raise ValueError("start_date must be on or before end_date")

    logger.info(f"fut_index_daily 同步开始: {start} ~ {end}")
    futures_dir = ctx.cfg.data_dir / "futures"
    all_frames = []
    current = start
    while current <= end:
        try:
            df = ctx.fetcher.fetch_fut_index_daily(current)
            time.sleep(0.2)
            if not df.empty:
                all_frames.append(df)
        except Exception as e:
            logger.error(f"fut_index_daily {current} 拉取失败: {e}")
            ctx.notifier.send(f"fut_index_daily {current} 拉取失败: {e}")
        current += timedelta(days=1)

    if not all_frames:
        msg = "fut_index_daily 无数据，跳过"
        logger.info(msg)
        ctx.notifier.send(msg)
        return

    combined = pd.concat(all_frames, ignore_index=True)
    success = 0
    skipped_existing = 0
    frontier = last

    for trade_date_value, part in combined.groupby("trade_date"):
        trade_date = parse_tushare_date(trade_date_value)
        if daily_partition_exists(futures_dir, "fut_index_daily", trade_date):
            skipped_existing += 1
            continue
        write_daily_partition(futures_dir, "fut_index_daily", trade_date, part.reset_index(drop=True))
        if frontier is None or trade_date > frontier:
            ctx.meta.update_last_date("fut_index_daily", trade_date)
            frontier = trade_date
        success += 1

    msg = (
        f"fut_index_daily 同步完成: 成功 {success} 天, "
        f"跳过已存在 {skipped_existing} 天"
    )
    logger.info(msg)
    ctx.notifier.send(msg)


def sync_fut_weekly_detail(ctx: SyncContext, start_date: date | None = None, end_date: date | None = None) -> None:
    today = date.today()
    last = ctx.meta.get_last_date("fut_weekly_detail")

    if start_date is None:
        start = (last + timedelta(days=1)) if last else FIRST_DATE
        end = today
    else:
        start = start_date
        end = end_date or today

    if start > end:
        raise ValueError("start_date must be on or before end_date")

    futures_dir = ctx.cfg.data_dir / "futures"
    success = 0
    skipped_existing = 0
    frontier = last
    weeks = week_ranges(start, end)
    logger.info(f"fut_weekly_detail 同步开始: {start} ~ {end}, 共 {len(weeks)} 个周")

    for week_num, week_start in weeks:
        try:
            df = ctx.fetcher.fetch_fut_weekly_detail(week_num)
            time.sleep(0.2)
            if df.empty:
                continue
            if daily_partition_exists(futures_dir, "fut_weekly_detail", week_start):
                skipped_existing += 1
                continue
            write_daily_partition(futures_dir, "fut_weekly_detail", week_start, df)
            if frontier is None or week_start > frontier:
                ctx.meta.update_last_date("fut_weekly_detail", week_start)
                frontier = week_start
            success += 1
        except Exception as e:
            logger.error(f"fut_weekly_detail {week_num} 同步失败: {e}")
            ctx.notifier.send(f"fut_weekly_detail {week_num} 同步失败: {e}")
            raise

    msg = (
        f"fut_weekly_detail 同步完成: 成功 {success} 周, "
        f"跳过已存在 {skipped_existing} 周, 共 {len(weeks)} 周"
    )
    logger.info(msg)
    ctx.notifier.send(msg)
