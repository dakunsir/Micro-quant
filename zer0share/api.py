import datetime as dt
from pathlib import Path

from zer0share.config import load_config
from zer0share.query import QueryContext
from zer0share.query import calendar, stock, index, industry, futures, options, etf


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

    def universe(self, **kwargs):
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
        dispatch = {
            "stock_basic": self.stock_basic,
            "trade_cal": self.trade_cal,
            "daily": self.daily,
            "adj_factor": self.adj_factor,
            "daily_basic": self.daily_basic,
            "stock_st": self.stock_st,
            "suspend_d": self.suspend_d,
            "stk_limit": self.stk_limit,
            "index_daily": self.index_daily,
            "index_weight": self.index_weight,
            "sw_daily": self.sw_daily,
            "idx_anns": self.idx_anns,
            "universe": self.universe,
            "pro_bar": self.pro_bar,
            "index_classify": self.index_classify,
            "sw_classify": self.index_classify,
            "index_member_all": self.index_member_all,
            "sw_member": self.index_member_all,
            "ci_index_member": self.ci_index_member,
            "ci_member": self.ci_index_member,
            "fut_basic": self.fut_basic,
            "fut_daily": self.fut_daily,
            "fut_holding": self.fut_holding,
            "fut_wsr": self.fut_wsr,
            "fut_settle": self.fut_settle,
            "fut_mapping": self.fut_mapping,
            "ft_limit": self.ft_limit,
            "fut_weekly": self.fut_weekly,
            "fut_monthly": self.fut_monthly,
            "fut_index_daily": self.fut_index_daily,
            "fut_weekly_detail": self.fut_weekly_detail,
            "opt_basic": self.opt_basic,
            "opt_daily": self.opt_daily,
            "etf_basic": self.etf_basic,
            "etf_index": self.etf_index,
            "fund_daily": self.fund_daily,
            "fund_adj": self.fund_adj,
            "etf_share_size": self.etf_share_size,
            "etf_sh_cons": self.etf_sh_cons,
        }
        try:
            method = dispatch[api_name]
        except KeyError as e:
            raise ValueError(f"unknown api: {api_name}") from e
        return method(**kwargs)


def pro_api(config_path="config/settings.toml") -> LocalPro:
    cfg = load_config(Path(config_path))
    return LocalPro(cfg.data_dir)
