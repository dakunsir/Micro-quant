from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from loguru import logger

import zer0share.dateutil as dateutil
from zer0share.storage import MetaStore

if TYPE_CHECKING:
    from zer0share.sync import SyncRuntime


class TradingCalendar:
    def __init__(self, meta: MetaStore, today_fn: Callable[[], str] = dateutil.today):
        self._meta = meta
        self._today_fn = today_fn

    def today(self) -> str:
        return self._today_fn()

    def load_from_parquet(self, data_dir: Path, exchanges: list[str] | None = None) -> None:
        self._meta.load_trade_cal_from_parquet(data_dir, exchanges)

    def get_trading_days(self, exchange: str, start: str, end: str) -> list[str]:
        return self._meta.get_trading_days(exchange, start, end)

    def get_week_end_trading_days(self, exchange: str, start: str, end: str) -> list[str]:
        """Return only the last trading day of each ISO week in [start, end]."""
        days = self._meta.get_trading_days(exchange, start, end)
        result, prev_week = [], None
        for d in days:
            dt = dateutil.parse_date(d)
            week = (dt.isocalendar()[0], dt.isocalendar()[1])
            if week != prev_week:
                if prev_week is not None:
                    result.append(last)
                prev_week = week
            last = d
        if prev_week is not None:
            result.append(last)
        return result

    def get_month_end_trading_days(self, exchange: str, start: str, end: str) -> list[str]:
        """Return only the last trading day of each calendar month in [start, end]."""
        days = self._meta.get_trading_days(exchange, start, end)
        result, prev_month = [], None
        for d in days:
            dt = dateutil.parse_date(d)
            month = (dt.year, dt.month)
            if month != prev_month:
                if prev_month is not None:
                    result.append(last)
                prev_month = month
            last = d
        if prev_month is not None:
            result.append(last)
        return result

    def is_trading_day(self, exchange: str, cal_date: str) -> bool:
        return self._meta.is_trading_day(exchange, cal_date)

    def skip_if_not_trading(self, exchange: str) -> bool:
        today = self.today()
        if not self.is_trading_day(exchange, today):
            logger.info(f"今日 {today} 非交易日，跳过同步")
            return True
        return False

    def ensure_loaded(self, rt: "SyncRuntime") -> None:
        if self._meta.get_last_date("trade_cal") is None:
            raise RuntimeError(
                "交易日历未加载。请先运行: python main.py sync --table trade_cal"
            )
