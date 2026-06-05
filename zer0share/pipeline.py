from datetime import date

from zer0share.config import Config
from zer0share.fetcher import TushareFetcher
from zer0share.notifier import Notifier
from zer0share.storage import MetaStore
from zer0share.sync import SyncContext
from zer0share.sync import calendar, equities, industry, futures, options
from zer0share.sync._helpers import EXCHANGES, ALL_EXCHANGES, skip_if_not_trading, ensure_trade_cal_loaded


class Pipeline:
    def __init__(self, cfg: Config, fetcher: TushareFetcher, notifier: Notifier):
        self._ctx = SyncContext(cfg, fetcher, notifier, MetaStore(cfg.db_path))

    @property
    def _meta(self):
        return self._ctx.meta

    @property
    def _fetcher(self):
        return self._ctx.fetcher

    @property
    def _notifier(self):
        return self._ctx.notifier

    def _ensure_trade_cal_loaded(self) -> None:
        ensure_trade_cal_loaded(self._ctx)

    def _skip_if_not_trading(self, exchange: str) -> bool:
        return skip_if_not_trading(self._ctx, exchange)

    # Calendar
    def sync_trade_cal(self):
        calendar.sync_trade_cal(self._ctx)

    # Equities
    def sync_basic(self):
        equities.sync_basic(self._ctx)

    def sync_daily_kline(self, start_date: date | None = None, end_date: date | None = None):
        equities.sync_daily_kline(self._ctx, start_date, end_date)

    def sync_adj_factor(self, start_date: date | None = None, end_date: date | None = None):
        equities.sync_adj_factor(self._ctx, start_date, end_date)

    def sync_daily_basic(self, start_date: date | None = None, end_date: date | None = None):
        equities.sync_daily_basic(self._ctx, start_date, end_date)

    def sync_stock_st(self, start_date: date | None = None, end_date: date | None = None):
        equities.sync_stock_st(self._ctx, start_date, end_date)

    def sync_suspend_d(self, start_date: date | None = None, end_date: date | None = None):
        equities.sync_suspend_d(self._ctx, start_date, end_date)

    def sync_stk_limit(self, start_date: date | None = None, end_date: date | None = None):
        equities.sync_stk_limit(self._ctx, start_date, end_date)

    def sync_index_weight(self, start_date: date | None = None, end_date: date | None = None):
        equities.sync_index_weight(self._ctx, start_date, end_date)

    def sync_index_daily(self, start_date: date | None = None, end_date: date | None = None):
        equities.sync_index_daily(self._ctx, start_date, end_date)

    # Industry
    def sync_industry(self):
        industry.sync_industry(self._ctx)

    def sync_ci_member(self):
        industry.sync_ci_member(self._ctx)

    # Futures
    def sync_fut_basic(self):
        futures.sync_fut_basic(self._ctx)

    def sync_fut_daily(self, start_date: date | None = None, end_date: date | None = None):
        futures.sync_fut_daily(self._ctx, start_date, end_date)

    def sync_fut_holding(self, start_date: date | None = None, end_date: date | None = None):
        futures.sync_fut_holding(self._ctx, start_date, end_date)

    def sync_fut_wsr(self, start_date: date | None = None, end_date: date | None = None):
        futures.sync_fut_wsr(self._ctx, start_date, end_date)

    def sync_fut_settle(self, start_date: date | None = None, end_date: date | None = None):
        futures.sync_fut_settle(self._ctx, start_date, end_date)

    def sync_fut_mapping(self, start_date: date | None = None, end_date: date | None = None):
        futures.sync_fut_mapping(self._ctx, start_date, end_date)

    def sync_ft_limit(self, start_date: date | None = None, end_date: date | None = None):
        futures.sync_ft_limit(self._ctx, start_date, end_date)

    def sync_fut_weekly(self, start_date: date | None = None, end_date: date | None = None):
        futures.sync_fut_weekly(self._ctx, start_date, end_date)

    def sync_fut_monthly(self, start_date: date | None = None, end_date: date | None = None):
        futures.sync_fut_monthly(self._ctx, start_date, end_date)

    def sync_fut_index_daily(self, start_date: date | None = None, end_date: date | None = None):
        futures.sync_fut_index_daily(self._ctx, start_date, end_date)

    def sync_fut_weekly_detail(self, start_date: date | None = None, end_date: date | None = None):
        futures.sync_fut_weekly_detail(self._ctx, start_date, end_date)

    # Options
    def sync_opt_basic(self):
        options.sync_opt_basic(self._ctx)

    def sync_opt_daily(self, start_date: date | None = None, end_date: date | None = None):
        options.sync_opt_daily(self._ctx, start_date, end_date)

    def close(self):
        self._ctx.meta.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
        return False
