import time
from datetime import date, timedelta
from loguru import logger

import pandas as pd

from zer0share.storage import (
    daily_partition_exists, write_basic,
    write_daily_partition, write_index_weight, index_weight_partition_exists,
)
from zer0share.sync import SyncContext
from zer0share.sync._helpers import (
    FIRST_DATE, INDEX_CODES, index_weight_meta_key,
    month_ranges, parse_tushare_date, should_log_progress, skip_if_not_trading,
    sync_daily_partitioned,
)
from zer0share.fetcher import INDEX_DAILY_CODES


def sync_basic(ctx: SyncContext) -> None:
    if skip_if_not_trading(ctx, "SSE"):
        return
    today = date.today()
    try:
        df = ctx.fetcher.fetch_basic()
        write_basic(ctx.cfg.data_dir, df)
        ctx.meta.update_last_date("basic", today)
        logger.info(f"basic 同步完成: {len(df)} 条")
    except Exception as e:
        logger.error(f"basic 同步失败: {e}")
        ctx.notifier.send(f"basic 同步失败: {e}")
        raise


def sync_daily_kline(ctx: SyncContext, start_date: date | None = None, end_date: date | None = None) -> None:
    sync_daily_partitioned(ctx, "daily_kline", ctx.fetcher.fetch_daily_kline, start_date, end_date)


def sync_adj_factor(ctx: SyncContext, start_date: date | None = None, end_date: date | None = None) -> None:
    sync_daily_partitioned(ctx, "adj_factor", ctx.fetcher.fetch_adj_factor, start_date, end_date)


def sync_daily_basic(ctx: SyncContext, start_date: date | None = None, end_date: date | None = None) -> None:
    sync_daily_partitioned(ctx, "daily_basic", ctx.fetcher.fetch_daily_basic, start_date, end_date)


def sync_stock_st(ctx: SyncContext, start_date: date | None = None, end_date: date | None = None) -> None:
    sync_daily_partitioned(ctx, "stock_st", ctx.fetcher.fetch_stock_st, start_date, end_date, write_empty=True)


def sync_suspend_d(ctx: SyncContext, start_date: date | None = None, end_date: date | None = None) -> None:
    sync_daily_partitioned(ctx, "suspend_d", ctx.fetcher.fetch_suspend_d, start_date, end_date, write_empty=True)


def sync_stk_limit(ctx: SyncContext, start_date: date | None = None, end_date: date | None = None) -> None:
    sync_daily_partitioned(ctx, "stk_limit", ctx.fetcher.fetch_stk_limit, start_date, end_date)


def sync_index_weight(ctx: SyncContext, start_date: date | None = None, end_date: date | None = None) -> None:
    today = date.today()
    end = end_date or today
    if start_date is not None and start_date > end:
        raise ValueError("start_date must be on or before end_date")

    success = 0
    skipped_existing = 0
    empty_months = 0
    requests = 0
    coverage_dates: list[date] = []
    for index_code in INDEX_CODES:
        meta_key = index_weight_meta_key(index_code)
        last = ctx.meta.get_last_date(meta_key)
        start = start_date or ((last + timedelta(days=1)) if last else FIRST_DATE)
        if start > end:
            logger.info(f"index_weight {index_code} 已覆盖到 {last}，无需同步")
            if last is not None:
                coverage_dates.append(last)
            continue

        ranges = month_ranges(start, end)
        logger.info(
            f"index_weight {index_code} 同步开始: {start} ~ {end}, "
            f"共 {len(ranges)} 个月度窗口"
        )
        try:
            for processed, (month_start, month_end) in enumerate(ranges, start=1):
                df = ctx.fetcher.fetch_index_weight(index_code, month_start, month_end)
                requests += 1
                time.sleep(0.2)
                if df.empty:
                    empty_months += 1
                else:
                    for trade_date_value, part in df.groupby("trade_date"):
                        trade_date = parse_tushare_date(trade_date_value)
                        if index_weight_partition_exists(ctx.cfg.data_dir, index_code, trade_date):
                            skipped_existing += 1
                            continue
                        write_index_weight(ctx.cfg.data_dir, index_code, trade_date, part)
                        success += 1

                if should_log_progress(processed, len(ranges)):
                    percent = processed / len(ranges) * 100
                    logger.info(
                        f"index_weight {index_code} 同步进度: "
                        f"{processed}/{len(ranges)} ({percent:.1f}%), "
                        f"当前窗口 {month_start} ~ {month_end}, "
                        f"成功 {success} 个分区, 空窗口 {empty_months} 个, "
                        f"跳过已存在 {skipped_existing} 个分区"
                    )

            frontier = max(last, end) if last is not None else end
            ctx.meta.update_last_date(meta_key, frontier)
            coverage_dates.append(frontier)
        except Exception as e:
            logger.error(f"index_weight {index_code} 同步失败: {e}")
            ctx.notifier.send(f"index_weight {index_code} 同步失败: {e}")
            raise

    if coverage_dates:
        ctx.meta.update_last_date("index_weight", min(coverage_dates))

    msg = (
        f"index_weight 同步完成: 成功 {success} 个分区, "
        f"空窗口 {empty_months} 个, 跳过已存在 {skipped_existing} 个分区, "
        f"请求 {requests} 次"
    )
    logger.info(msg)
    ctx.notifier.send(msg)


def sync_index_daily(ctx: SyncContext, start_date: date | None = None, end_date: date | None = None) -> None:
    today = date.today()
    last = ctx.meta.get_last_date("index_daily")

    if start_date is None:
        start = (last + timedelta(days=1)) if last else FIRST_DATE
        end = today
    else:
        start = start_date
        end = end_date or today

    if start_date is None and start > end:
        logger.info("index_daily 已是最新，无需同步")
        return
    if start > end:
        raise ValueError("start_date must be on or before end_date")

    logger.info(f"index_daily 同步开始: {start} ~ {end}, 共 {len(INDEX_DAILY_CODES)} 个指数")
    all_frames = []
    for ts_code in INDEX_DAILY_CODES:
        try:
            df = ctx.fetcher.fetch_index_daily(ts_code, start, end)
            time.sleep(0.2)
            if not df.empty:
                all_frames.append(df)
        except Exception as e:
            logger.error(f"index_daily {ts_code} 拉取失败: {e}")
            ctx.notifier.send(f"index_daily {ts_code} 拉取失败: {e}")
            continue

    if not all_frames:
        msg = "index_daily 无数据，跳过"
        logger.info(msg)
        ctx.notifier.send(msg)
        return

    combined = pd.concat(all_frames, ignore_index=True)
    success = 0
    skipped_existing = 0
    frontier = last

    for trade_date_value, part in combined.groupby("trade_date"):
        trade_date = parse_tushare_date(trade_date_value)
        if daily_partition_exists(ctx.cfg.data_dir, "index_daily", trade_date):
            skipped_existing += 1
            continue
        write_daily_partition(
            ctx.cfg.data_dir, "index_daily", trade_date, part.reset_index(drop=True)
        )
        if frontier is None or trade_date > frontier:
            ctx.meta.update_last_date("index_daily", trade_date)
            frontier = trade_date
        success += 1

    msg = (
        f"index_daily 同步完成: 成功 {success} 天, "
        f"跳过已存在 {skipped_existing} 天, 共 {len(INDEX_DAILY_CODES)} 个指数"
    )
    logger.info(msg)
    ctx.notifier.send(msg)
