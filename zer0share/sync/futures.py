import time
import pandas as pd
from loguru import logger

import zer0share.dateutil as dateutil
from zer0share.fetcher import FUTURES_EXCHANGES
from zer0share.storage import DailyPartitionStore, SnapshotStore
from zer0share.sync import SyncRuntime
from zer0share.sync._jobs import DailySyncJob, SyncJob
from zer0share.catalog import (
    FT_LIMIT_SPEC, FUT_BASIC_SPEC, FUT_DAILY_SPEC, FUT_HOLDING_SPEC,
    FUT_INDEX_DAILY_SPEC, FUT_MAPPING_SPEC, FUT_MONTHLY_SPEC,
    FUT_SETTLE_SPEC, FUT_WEEKLY_DETAIL_SPEC, FUT_WEEKLY_SPEC, FUT_WSR_SPEC,
)


class FutBasicSyncJob(SyncJob):
    table_name = "fut_basic"
    supports_date_range = False

    def __init__(self, fetch, store: SnapshotStore):
        self._fetch = fetch
        self._store = store

    def run(self, rt: SyncRuntime, start_date=None, end_date=None) -> None:
        today = rt.calendar.today()
        all_frames = []
        try:
            for exchange in FUTURES_EXCHANGES:
                for fut_type in ("1", "2"):
                    df = self._fetch(exchange, fut_type)
                    time.sleep(0.2)
                    if not df.empty:
                        all_frames.append(df)
            combined = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()
            self._store.write(combined)
            rt.meta.update_last_date("fut_basic", today)
            logger.info(f"fut_basic 同步完成: {len(combined)} 条")
        except Exception as e:
            logger.error(f"fut_basic 同步失败: {e}")
            rt.notifier.send(f"fut_basic 同步失败: {e}")
            raise


class FutIndexDailySyncJob(SyncJob):
    """Bug3 fix: iterates trading days only (not all calendar days)."""
    table_name = "fut_index_daily"
    supports_date_range = True

    def __init__(self, fetch, store: DailyPartitionStore):
        self._fetch = fetch
        self._store = store

    def run(self, rt: SyncRuntime, start_date=None, end_date=None) -> None:
        if rt.calendar.skip_if_not_trading("SSE"):
            return
        today = rt.calendar.today()
        last = rt.meta.get_last_date("fut_index_daily")

        if start_date is None:
            start = dateutil.add_days(last, 1) if last else FUT_INDEX_DAILY_SPEC.first_date
            end = today
            if start > end:
                logger.info("fut_index_daily 已是最新，无需同步")
                return
        else:
            start = start_date
            end = end_date or today
            if start > end:
                raise ValueError("start_date must be on or before end_date")

        # Bug3 fix: use trading days, not all calendar days
        trading_days = rt.calendar.get_trading_days("SSE", start, end)
        logger.info(f"fut_index_daily 同步开始: {start} ~ {end}, {len(trading_days)} 个交易日")
        all_frames = []

        for trade_date in trading_days:
            try:
                df = self._fetch(trade_date)
                time.sleep(0.2)
                if not df.empty:
                    all_frames.append(df)
            except Exception as e:
                logger.error(f"fut_index_daily {trade_date} 拉取失败: {e}")
                rt.notifier.send(f"fut_index_daily {trade_date} 拉取失败: {e}")

        if not all_frames:
            msg = "fut_index_daily 无数据，跳过"
            logger.info(msg)
            rt.notifier.send(msg)
            return

        combined = pd.concat(all_frames, ignore_index=True)
        success = skipped_existing = 0
        frontier = last

        for trade_date_value, part in combined.groupby("trade_date"):
            trade_date = str(trade_date_value)
            if self._store.exists(trade_date):
                skipped_existing += 1
                continue
            self._store.write(trade_date, part.reset_index(drop=True))
            if frontier is None or trade_date > frontier:
                rt.meta.update_last_date("fut_index_daily", trade_date)
                frontier = trade_date
            success += 1

        msg = f"fut_index_daily 同步完成: 成功 {success} 天, 跳过已存在 {skipped_existing} 天"
        logger.info(msg)
        rt.notifier.send(msg)


class FutWeeklyDetailSyncJob(SyncJob):
    """Bug1+Bug2 fix: check existence before fetch; graceful up-to-date return."""
    table_name = "fut_weekly_detail"
    supports_date_range = True

    def __init__(self, fetch, store: DailyPartitionStore):
        self._fetch = fetch
        self._store = store

    def run(self, rt: SyncRuntime, start_date=None, end_date=None) -> None:
        today = rt.calendar.today()
        last = rt.meta.get_last_date("fut_weekly_detail")

        if start_date is None:
            start = dateutil.add_days(last, 1) if last else FUT_WEEKLY_DETAIL_SPEC.first_date
            end = today
            if start > end:  # Bug2 fix: graceful return
                logger.info("fut_weekly_detail 已是最新，无需同步")
                return
        else:
            start = start_date
            end = end_date or today
            if start > end:
                raise ValueError("start_date must be on or before end_date")

        weeks = dateutil.week_ranges(start, end)
        logger.info(f"fut_weekly_detail 同步开始: {start} ~ {end}, 共 {len(weeks)} 个周")
        success = skipped_existing = 0
        frontier = last

        for week_num, week_start in weeks:
            if self._store.exists(week_start):  # Bug1 fix: check before fetch
                skipped_existing += 1
                continue
            try:
                df = self._fetch(week_num)
                time.sleep(0.2)
                if df.empty:
                    continue
                self._store.write(week_start, df)
                if frontier is None or week_start > frontier:
                    rt.meta.update_last_date("fut_weekly_detail", week_start)
                    frontier = week_start
                success += 1
            except Exception as e:
                logger.error(f"fut_weekly_detail {week_num} 同步失败: {e}")
                rt.notifier.send(f"fut_weekly_detail {week_num} 同步失败: {e}")
                raise

        msg = (
            f"fut_weekly_detail 同步完成: 成功 {success} 周, "
            f"跳过已存在 {skipped_existing} 周, 共 {len(weeks)} 周"
        )
        logger.info(msg)
        rt.notifier.send(msg)


def build_jobs(cfg, fetcher) -> list[SyncJob]:
    fd = cfg.data_dir / "futures"
    return [
        FutBasicSyncJob(fetch=fetcher.fetch_fut_basic, store=SnapshotStore(fd / "fut_basic" / "data.parquet")),
        DailySyncJob(
            table_name=FUT_DAILY_SPEC.name, spec=FUT_DAILY_SPEC,
            fetch=fetcher.fetch_fut_daily, store=DailyPartitionStore(fd / "fut_daily"),
        ),
        DailySyncJob(
            table_name=FUT_HOLDING_SPEC.name, spec=FUT_HOLDING_SPEC,
            fetch=fetcher.fetch_fut_holding, store=DailyPartitionStore(fd / "fut_holding"),
        ),
        DailySyncJob(
            table_name=FUT_WSR_SPEC.name, spec=FUT_WSR_SPEC,
            fetch=fetcher.fetch_fut_wsr, store=DailyPartitionStore(fd / "fut_wsr"),
        ),
        DailySyncJob(
            table_name=FUT_SETTLE_SPEC.name, spec=FUT_SETTLE_SPEC,
            fetch=fetcher.fetch_fut_settle, store=DailyPartitionStore(fd / "fut_settle"),
        ),
        DailySyncJob(
            table_name=FUT_MAPPING_SPEC.name, spec=FUT_MAPPING_SPEC,
            fetch=fetcher.fetch_fut_mapping, store=DailyPartitionStore(fd / "fut_mapping"),
        ),
        DailySyncJob(
            table_name=FT_LIMIT_SPEC.name, spec=FT_LIMIT_SPEC,
            fetch=fetcher.fetch_ft_limit, store=DailyPartitionStore(fd / "ft_limit"),
        ),
        DailySyncJob(
            table_name=FUT_WEEKLY_SPEC.name, spec=FUT_WEEKLY_SPEC,
            fetch=fetcher.fetch_fut_weekly, store=DailyPartitionStore(fd / "fut_weekly"),
            period="week",
        ),
        DailySyncJob(
            table_name=FUT_MONTHLY_SPEC.name, spec=FUT_MONTHLY_SPEC,
            fetch=fetcher.fetch_fut_monthly, store=DailyPartitionStore(fd / "fut_monthly"),
            period="month",
        ),
        FutIndexDailySyncJob(
            fetch=fetcher.fetch_fut_index_daily,
            store=DailyPartitionStore(fd / "fut_index_daily"),
        ),
        FutWeeklyDetailSyncJob(
            fetch=fetcher.fetch_fut_weekly_detail,
            store=DailyPartitionStore(fd / "fut_weekly_detail"),
        ),
    ]
