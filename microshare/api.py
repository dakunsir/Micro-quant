import datetime as dt
from pathlib import Path

from microshare.config import load_config
from microshare.query import QueryContext
from microshare.query import calendar, stock, index, industry, futures, options, etf


READ_ONLY_QUERY_METHODS = {
    "stock_basic": "stock_basic",
    "trade_cal": "trade_cal",
    "daily": "daily",
    "adj_factor": "adj_factor",
    "daily_basic": "daily_basic",
    "stock_st": "stock_st",
    "suspend_d": "suspend_d",
    "stk_limit": "stk_limit",
    "index_daily": "index_daily",
    "index_weight": "index_weight",
    "sw_daily": "sw_daily",
    "idx_anns": "idx_anns",
    "universe": "universe",
    "pro_bar": "pro_bar",
    "index_classify": "index_classify",
    "sw_classify": "index_classify",
    "index_member_all": "index_member_all",
    "sw_member": "index_member_all",
    "ci_index_member": "ci_index_member",
    "ci_member": "ci_index_member",
    "fut_basic": "fut_basic",
    "fut_daily": "fut_daily",
    "fut_holding": "fut_holding",
    "fut_wsr": "fut_wsr",
    "fut_settle": "fut_settle",
    "fut_mapping": "fut_mapping",
    "ft_limit": "ft_limit",
    "fut_weekly": "fut_weekly",
    "fut_monthly": "fut_monthly",
    "fut_index_daily": "fut_index_daily",
    "fut_weekly_detail": "fut_weekly_detail",
    "opt_basic": "opt_basic",
    "opt_daily": "opt_daily",
    "etf_basic": "etf_basic",
    "etf_index": "etf_index",
    "fund_daily": "fund_daily",
    "fund_adj": "fund_adj",
    "etf_share_size": "etf_share_size",
    "etf_sh_cons": "etf_sh_cons",
}


def _check_dates(kwargs: dict) -> None:
    for key in ("start_date", "end_date", "trade_date", "ann_date", "pub_date", "base_date"):
        val = kwargs.get(key)
        if val is not None:
            try:
                dt.datetime.strptime(val, "%Y%m%d")
            except ValueError:
                raise ValueError(f"invalid date format: {val!r}; expected YYYYMMDD")


class LocalPro:
    def __init__(self, data_dir):
        self._ctx = QueryContext(Path(data_dir))

    # Calendar
    def trade_cal(self, **kwargs):
        _check_dates(kwargs)
        return calendar.trade_cal(self._ctx, **kwargs)

    # Equities
    def stock_basic(self, **kwargs):
        return stock.stock_basic(self._ctx, **kwargs)

    def daily(self, **kwargs):
        _check_dates(kwargs)
        return stock.daily(self._ctx, **kwargs)

    def adj_factor(self, **kwargs):
        _check_dates(kwargs)
        return stock.adj_factor(self._ctx, **kwargs)

    def daily_basic(self, **kwargs):
        _check_dates(kwargs)
        return stock.daily_basic(self._ctx, **kwargs)

    def stock_st(self, **kwargs):
        _check_dates(kwargs)
        return stock.stock_st(self._ctx, **kwargs)

    def suspend_d(self, **kwargs):
        _check_dates(kwargs)
        return stock.suspend_d(self._ctx, **kwargs)

    def stk_limit(self, **kwargs):
        _check_dates(kwargs)
        return stock.stk_limit(self._ctx, **kwargs)

    def index_daily(self, **kwargs):
        _check_dates(kwargs)
        return index.index_daily(self._ctx, **kwargs)

    def index_weight(self, **kwargs):
        _check_dates(kwargs)
        return index.index_weight(self._ctx, **kwargs)

    def sw_daily(self, **kwargs):
        _check_dates(kwargs)
        return index.sw_daily(self._ctx, **kwargs)

    def idx_anns(self, **kwargs):
        _check_dates(kwargs)
        return index.idx_anns(self._ctx, **kwargs)

    def universe(self, universe=None, **kwargs):
        if universe is not None:
            if "universe" in kwargs:
                raise TypeError("universe was provided both positionally and by keyword")
            kwargs["universe"] = universe
        _check_dates(kwargs)
        return stock.universe(self._ctx, **kwargs)

    def pro_bar(self, **kwargs):
        _check_dates(kwargs)
        return stock.pro_bar(self._ctx, **kwargs)

    # Industry
    def index_classify(self, **kwargs):
        return industry.index_classify(self._ctx, **kwargs)

    def index_member_all(self, **kwargs):
        return industry.index_member_all(self._ctx, **kwargs)

    def ci_index_member(self, **kwargs):
        return industry.ci_index_member(self._ctx, **kwargs)

    # Futures
    def fut_basic(self, **kwargs):
        return futures.fut_basic(self._ctx, **kwargs)

    def fut_daily(self, **kwargs):
        _check_dates(kwargs)
        return futures.fut_daily(self._ctx, **kwargs)

    def fut_holding(self, **kwargs):
        _check_dates(kwargs)
        return futures.fut_holding(self._ctx, **kwargs)

    def fut_wsr(self, **kwargs):
        _check_dates(kwargs)
        return futures.fut_wsr(self._ctx, **kwargs)

    def fut_settle(self, **kwargs):
        _check_dates(kwargs)
        return futures.fut_settle(self._ctx, **kwargs)

    def fut_mapping(self, **kwargs):
        _check_dates(kwargs)
        return futures.fut_mapping(self._ctx, **kwargs)

    def ft_limit(self, **kwargs):
        _check_dates(kwargs)
        return futures.ft_limit(self._ctx, **kwargs)

    def fut_weekly(self, **kwargs):
        _check_dates(kwargs)
        return futures.fut_weekly(self._ctx, **kwargs)

    def fut_monthly(self, **kwargs):
        _check_dates(kwargs)
        return futures.fut_monthly(self._ctx, **kwargs)

    def fut_index_daily(self, **kwargs):
        _check_dates(kwargs)
        return futures.fut_index_daily(self._ctx, **kwargs)

    def fut_weekly_detail(self, **kwargs):
        _check_dates(kwargs)
        return futures.fut_weekly_detail(self._ctx, **kwargs)

    # Options
    def opt_basic(self, **kwargs):
        return options.opt_basic(self._ctx, **kwargs)

    def opt_daily(self, **kwargs):
        _check_dates(kwargs)
        return options.opt_daily(self._ctx, **kwargs)

    # ETF
    def etf_basic(self, **kwargs):
        _check_dates(kwargs)
        return etf.etf_basic(self._ctx, **kwargs)

    def etf_index(self, **kwargs):
        _check_dates(kwargs)
        return etf.etf_index(self._ctx, **kwargs)

    def fund_daily(self, **kwargs):
        _check_dates(kwargs)
        return etf.fund_daily(self._ctx, **kwargs)

    def fund_adj(self, **kwargs):
        _check_dates(kwargs)
        return etf.fund_adj(self._ctx, **kwargs)

    def etf_share_size(self, **kwargs):
        _check_dates(kwargs)
        return etf.etf_share_size(self._ctx, **kwargs)

    def etf_sh_cons(self, **kwargs):
        _check_dates(kwargs)
        return etf.etf_sh_cons(self._ctx, **kwargs)

    def query(self, api_name: str, **kwargs):
        try:
            method_name = READ_ONLY_QUERY_METHODS[api_name]
        except KeyError as e:
            raise ValueError(f"unknown api: {api_name}") from e
        return getattr(self, method_name)(**kwargs)


def pro_api(config_path="config/settings.toml") -> LocalPro:
    cfg = load_config(Path(config_path))
    return LocalPro(cfg.data_dir)
