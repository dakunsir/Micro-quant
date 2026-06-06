"""
sync/_jobs.py — Abstract and concrete sync job implementations.

SyncJob          ABC with table_name, supports_date_range, abstract run()
DailySyncJob     Daily-partitioned table sync (loops over trading days)
SnapshotSyncJob  Single-file snapshot table sync
"""
import time
from abc import ABC, abstractmethod
from typing import Callable

import pandas as pd
from loguru import logger

import zer0share.dateutil as dateutil
from zer0share.query.repository import DailyTableSpec, TableSpec
from zer0share.storage import DailyPartitionStore, SnapshotStore
from zer0share.sync import SyncRuntime

FIRST_DATE = "20160101"
PROGRESS_INTERVAL = 50


class SyncJob(ABC):
    table_name: str
    supports_date_range: bool

    @abstractmethod
    def run(self, rt: SyncRuntime, start_date: str | None = None, end_date: str | None = None) -> None:
        ...


class DailySyncJob(SyncJob):
    def __init__(
        self,
        table_name: str,
        spec: DailyTableSpec,
        fetch: Callable[[str], pd.DataFrame],
        store: DailyPartitionStore,
        write_empty: bool = False,
        exchange: str = "SSE",
        supports_date_range: bool = True,
    ):
        self.table_name = table_name
        self.spec = spec
        self.fetch = fetch
        self.store = store
        self.write_empty = write_empty
        self.exchange = exchange
        self.supports_date_range = supports_date_range

    def run(
        self,
        rt: SyncRuntime,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> None:
        today = rt.calendar.today()

        if start_date is None:
            last = rt.meta.get_last_date(self.spec.name)
            start = dateutil.add_days(last, 1) if last is not None else FIRST_DATE
            end = today
            if start > end:
                logger.info(f"{self.spec.name}: 已是最新 (last={last})")
                return
        else:
            start = start_date
            end = end_date if end_date is not None else today
            if start > end:
                raise ValueError(
                    f"start_date {start} is after end_date {end}"
                )

        trade_cal_loaded = rt.meta.get_last_date("trade_cal") is not None
        trading_days = rt.calendar.get_trading_days(self.exchange, start, end)

        if not trading_days and not trade_cal_loaded:
            raise RuntimeError(
                f"No trading days found for {self.exchange} between {start} and {end}. "
                "Trade calendar may not be loaded. Run `sync --table trade_cal` first."
            )

        success = 0
        empty = 0
        skipped_existing = 0
        current_meta = rt.meta.get_last_date(self.spec.name)

        for i, trade_date in enumerate(trading_days):
            if self.store.exists(trade_date):
                skipped_existing += 1
                continue

            try:
                df = self.fetch(trade_date)
            except Exception as exc:
                logger.error(f"{self.spec.name}: fetch failed on {trade_date}: {exc}")
                rt.notifier.send(
                    f"{self.spec.name} 同步失败 ({trade_date}): {exc}"
                )
                raise

            time.sleep(0.2)

            if df is not None and not df.empty:
                self.store.write(trade_date, df)
                if current_meta is None or trade_date > current_meta:
                    rt.meta.update_last_date(self.spec.name, trade_date)
                    current_meta = trade_date
                success += 1
            elif self.write_empty:
                self.store.write(trade_date, df if df is not None else pd.DataFrame())
                if current_meta is None or trade_date > current_meta:
                    rt.meta.update_last_date(self.spec.name, trade_date)
                    current_meta = trade_date
                empty += 1
            else:
                empty += 1

            if (i + 1) % PROGRESS_INTERVAL == 0:
                logger.info(
                    f"{self.spec.name}: progress {i + 1}/{len(trading_days)} "
                    f"success={success} empty={empty} skipped={skipped_existing}"
                )

        total = len(trading_days)
        logger.info(
            f"{self.spec.name}: done total={total} "
            f"success={success} empty={empty} skipped={skipped_existing}"
        )
        rt.notifier.send(
            f"{self.spec.name} 同步完成: "
            f"写入={success} 空={empty} 已存在={skipped_existing}"
        )


class SnapshotSyncJob(SyncJob):
    def __init__(
        self,
        table_name: str,
        spec: TableSpec,
        fetch: Callable[[], pd.DataFrame],
        store: SnapshotStore,
        skip_non_trading: bool = True,
        exchange: str = "SSE",
        supports_date_range: bool = False,
    ):
        self.table_name = table_name
        self.spec = spec
        self.fetch = fetch
        self.store = store
        self.skip_non_trading = skip_non_trading
        self.exchange = exchange
        self.supports_date_range = supports_date_range

    def run(
        self,
        rt: SyncRuntime,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> None:
        if self.skip_non_trading and rt.calendar.skip_if_not_trading(self.exchange):
            return

        today = rt.calendar.today()

        try:
            df = self.fetch()
        except Exception as exc:
            logger.error(f"{self.spec.name}: fetch failed: {exc}")
            rt.notifier.send(f"{self.spec.name} 同步失败: {exc}")
            raise

        self.store.write(df)
        rt.meta.update_last_date(self.spec.name, today)
        logger.info(f"{self.spec.name}: snapshot written ({len(df)} rows)")
        rt.notifier.send(f"{self.spec.name} 同步完成: {len(df)} 行")
