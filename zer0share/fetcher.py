import tushare as ts
import pandas as pd
import time
from datetime import date
from loguru import logger

from zer0share.schema import (
    BASIC_COLS, DAILY_COLS, TRADE_CAL_COLS, ADJ_FACTOR_COLS, DAILY_BASIC_COLS,
    STOCK_ST_COLS, SUSPEND_D_COLS, STK_LIMIT_COLS, INDEX_WEIGHT_COLS,
    INDEX_DAILY_COLS, SW_CLASSIFY_COLS, SW_MEMBER_COLS, CI_MEMBER_COLS,
    OPT_BASIC_COLS, OPT_DAILY_COLS, FUT_BASIC_COLS, FUT_DAILY_COLS,
    FUT_HOLDING_COLS, FUT_WSR_COLS, FUT_SETTLE_COLS, FUT_MAPPING_COLS,
    FT_LIMIT_COLS, FUT_WEEKLY_COLS, FUT_MONTHLY_COLS, FUT_INDEX_DAILY_COLS,
    FUT_WEEKLY_DETAIL_COLS,
)

INDEX_DAILY_CODES = [
    "000001.SH",  # 上证指数
    "399001.SZ",  # 深证成指
    "000016.SH",  # 上证50
    "000300.SH",  # 沪深300
    "000905.SH",  # 中证500
    "000852.SH",  # 中证1000
    "000985.SH",  # 中证全指
    "399006.SZ",  # 创业板指
    "000688.SH",  # 科创50
    "399005.SZ",  # 中小板指
    "000922.SH",  # 中证红利
    "932000.CSI", # 中证2000（代码待实测确认）
]

FUTURES_EXCHANGES = ["CZCE", "SHFE", "DCE", "CFFEX", "INE", "GFEX"]

OPTIONS_EXCHANGES = ["SSE", "SZSE", "CFFEX", "DCE", "SHFE", "CZCE"]


class TushareFetcher:
    def __init__(self, token: str):
        self._pro = ts.pro_api(token)

    def fetch_basic(self) -> pd.DataFrame:
        logger.info("拉取 stock_basic")
        df = self._pro.stock_basic(
            exchange="",
            list_status="L,D,P,G",
            fields=",".join(BASIC_COLS)
        )
        return df[BASIC_COLS]

    def fetch_daily_kline(self, trade_date: date) -> pd.DataFrame:
        date_str = trade_date.strftime("%Y%m%d")
        logger.debug(f"拉取日线行情: {date_str}")
        df = self._pro.daily(trade_date=date_str, fields=",".join(DAILY_COLS))
        if df is None or df.empty:
            return pd.DataFrame(columns=DAILY_COLS)
        return df[DAILY_COLS]

    def fetch_adj_factor(self, trade_date: date) -> pd.DataFrame:
        date_str = trade_date.strftime("%Y%m%d")
        logger.debug(f"拉取复权因子: {date_str}")
        df = self._pro.adj_factor(trade_date=date_str, fields=",".join(ADJ_FACTOR_COLS))
        if df is None or df.empty:
            return pd.DataFrame(columns=ADJ_FACTOR_COLS)
        return df[ADJ_FACTOR_COLS]

    def fetch_daily_basic(self, trade_date: date) -> pd.DataFrame:
        date_str = trade_date.strftime("%Y%m%d")
        logger.debug(f"拉取每日指标: {date_str}")
        df = self._pro.daily_basic(
            ts_code="",
            trade_date=date_str,
            fields=",".join(DAILY_BASIC_COLS),
        )
        return _select_columns_or_empty(df, DAILY_BASIC_COLS)

    def fetch_stock_st(self, trade_date: date) -> pd.DataFrame:
        date_str = trade_date.strftime("%Y%m%d")
        logger.debug(f"拉取ST股票列表: {date_str}")
        df = self._pro.stock_st(trade_date=date_str, fields=",".join(STOCK_ST_COLS))
        return _select_columns_or_empty(df, STOCK_ST_COLS)

    def fetch_suspend_d(self, trade_date: date) -> pd.DataFrame:
        date_str = trade_date.strftime("%Y%m%d")
        logger.debug(f"拉取每日停复牌: {date_str}")
        df = self._pro.suspend_d(
            trade_date=date_str,
            suspend_type="S",
            fields=",".join(SUSPEND_D_COLS),
        )
        return _select_columns_or_empty(df, SUSPEND_D_COLS)

    def fetch_stk_limit(self, trade_date: date) -> pd.DataFrame:
        date_str = trade_date.strftime("%Y%m%d")
        logger.debug(f"拉取每日涨跌停价格: {date_str}")
        df = self._pro.stk_limit(trade_date=date_str, fields=",".join(STK_LIMIT_COLS))
        return _select_columns_or_empty(df, STK_LIMIT_COLS)

    def fetch_index_weight(
        self, index_code: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        logger.debug(
            f"拉取指数成分: {index_code} "
            f"{start_date.strftime('%Y%m%d')}~{end_date.strftime('%Y%m%d')}"
        )
        df = self._pro.index_weight(
            index_code=index_code,
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            fields=",".join(INDEX_WEIGHT_COLS),
        )
        return _select_columns_or_empty(df, INDEX_WEIGHT_COLS)

    def fetch_index_daily(
        self, ts_code: str, start_date: date, end_date: date
    ) -> pd.DataFrame:
        logger.debug(
            f"拉取指数日线: {ts_code} "
            f"{start_date.strftime('%Y%m%d')}~{end_date.strftime('%Y%m%d')}"
        )
        df = self._pro.index_daily(
            ts_code=ts_code,
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            fields=",".join(INDEX_DAILY_COLS),
        )
        return _select_columns_or_empty(df, INDEX_DAILY_COLS)

    def fetch_trade_cal(
        self,
        exchange: str,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        start = start_date or date(1990, 1, 1)
        end = end_date or date.today()
        logger.info(
            f"拉取交易日历: {exchange} "
            f"{start.strftime('%Y%m%d')}~{end.strftime('%Y%m%d')}"
        )
        df = self._pro.trade_cal(
            exchange=exchange,
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            fields=",".join(TRADE_CAL_COLS),
        )
        if df is None or df.empty:
            return pd.DataFrame(columns=TRADE_CAL_COLS)
        df["is_open"] = df["is_open"].astype(str).map({"1": True, "0": False}).astype(object)
        return df[TRADE_CAL_COLS]

    def fetch_fut_basic(self, exchange: str, fut_type: str = "1") -> pd.DataFrame:
        logger.debug(f"拉取期货合约: exchange={exchange}, fut_type={fut_type}")
        df = self._pro.fut_basic(
            exchange=exchange,
            fut_type=fut_type,
            fields=",".join(FUT_BASIC_COLS),
        )
        if df is None or df.empty:
            return pd.DataFrame(columns=FUT_BASIC_COLS)
        return df[FUT_BASIC_COLS]

    def fetch_fut_daily(self, trade_date: date) -> pd.DataFrame:
        date_str = trade_date.strftime("%Y%m%d")
        logger.debug(f"拉取期货日线: {date_str}")
        df = self._pro.fut_daily(trade_date=date_str, fields=",".join(FUT_DAILY_COLS))
        return _select_columns_or_empty(df, FUT_DAILY_COLS)

    def fetch_fut_holding(self, trade_date: date) -> pd.DataFrame:
        date_str = trade_date.strftime("%Y%m%d")
        logger.debug(f"拉取期货持仓排名: {date_str}")
        df = self._pro.fut_holding(trade_date=date_str, fields=",".join(FUT_HOLDING_COLS))
        return _select_columns_or_empty(df, FUT_HOLDING_COLS)

    def fetch_fut_wsr(self, trade_date: date) -> pd.DataFrame:
        date_str = trade_date.strftime("%Y%m%d")
        logger.debug(f"拉取期货仓单: {date_str}")
        df = self._pro.fut_wsr(trade_date=date_str, fields=",".join(FUT_WSR_COLS))
        return _select_columns_or_empty(df, FUT_WSR_COLS)

    def fetch_fut_settle(self, trade_date: date) -> pd.DataFrame:
        date_str = trade_date.strftime("%Y%m%d")
        logger.debug(f"拉取期货结算参数: {date_str}")
        df = self._pro.fut_settle(trade_date=date_str, fields=",".join(FUT_SETTLE_COLS))
        return _select_columns_or_empty(df, FUT_SETTLE_COLS)

    def fetch_fut_mapping(self, trade_date: date) -> pd.DataFrame:
        date_str = trade_date.strftime("%Y%m%d")
        logger.debug(f"拉取期货主力映射: {date_str}")
        df = self._pro.fut_mapping(trade_date=date_str, fields=",".join(FUT_MAPPING_COLS))
        return _select_columns_or_empty(df, FUT_MAPPING_COLS)

    def fetch_ft_limit(self, trade_date: date) -> pd.DataFrame:
        date_str = trade_date.strftime("%Y%m%d")
        logger.debug(f"拉取期货涨跌停: {date_str}")
        df = self._pro.ft_limit(trade_date=date_str, fields=",".join(FT_LIMIT_COLS))
        return _select_columns_or_empty(df, FT_LIMIT_COLS)

    def fetch_fut_weekly(self, trade_date: date) -> pd.DataFrame:
        date_str = trade_date.strftime("%Y%m%d")
        logger.debug(f"拉取期货周线: {date_str}")
        df = self._pro.fut_weekly_monthly(
            trade_date=date_str, freq="week", fields=",".join(FUT_WEEKLY_COLS),
        )
        return _select_columns_or_empty(df, FUT_WEEKLY_COLS)

    def fetch_fut_monthly(self, trade_date: date) -> pd.DataFrame:
        date_str = trade_date.strftime("%Y%m%d")
        logger.debug(f"拉取期货月线: {date_str}")
        df = self._pro.fut_weekly_monthly(
            trade_date=date_str, freq="month", fields=",".join(FUT_MONTHLY_COLS),
        )
        return _select_columns_or_empty(df, FUT_MONTHLY_COLS)

    def fetch_fut_index_daily(self, trade_date: date) -> pd.DataFrame:
        date_str = trade_date.strftime("%Y%m%d")
        logger.debug(f"拉取南华期货指数: {date_str}")
        df = self._pro.fut_index_daily(
            trade_date=date_str, fields=",".join(FUT_INDEX_DAILY_COLS),
        )
        return _select_columns_or_empty(df, FUT_INDEX_DAILY_COLS)

    def fetch_fut_weekly_detail(self, week: str) -> pd.DataFrame:
        logger.debug(f"拉取期货品种周报: {week}")
        df = self._pro.fut_weekly_detail(
            week=week, fields=",".join(FUT_WEEKLY_DETAIL_COLS),
        )
        if df is None or df.empty:
            return pd.DataFrame(columns=FUT_WEEKLY_DETAIL_COLS)
        return df[FUT_WEEKLY_DETAIL_COLS]

    def fetch_opt_basic(self, exchange: str) -> pd.DataFrame:
        logger.debug(f"拉取期权合约: exchange={exchange}")
        df = self._pro.opt_basic(exchange=exchange, fields=",".join(OPT_BASIC_COLS))
        if df is None or df.empty:
            return pd.DataFrame(columns=OPT_BASIC_COLS)
        return df[OPT_BASIC_COLS]

    def fetch_opt_daily(self, trade_date: date) -> pd.DataFrame:
        date_str = trade_date.strftime("%Y%m%d")
        logger.debug(f"拉取期权日线: {date_str}")
        df = self._pro.opt_daily(trade_date=date_str, fields=",".join(OPT_DAILY_COLS))
        return _select_columns_or_empty(df, OPT_DAILY_COLS)

    SW_VERSIONS = ("SW2014", "SW2021")

    def fetch_sw_classify(self) -> pd.DataFrame:
        frames = []
        for src in self.SW_VERSIONS:
            logger.info(f"拉取申万行业分类: {src}")
            for level in ("L1", "L2", "L3"):
                df = self._pro.index_classify(level=level, src=src)
                if df is not None and not df.empty:
                    df["src"] = src
                    frames.append(df)
        if not frames:
            return pd.DataFrame(columns=SW_CLASSIFY_COLS)
        result = pd.concat(frames, ignore_index=True)
        return result[SW_CLASSIFY_COLS]

    def fetch_sw_member(self) -> pd.DataFrame:
        frames = []
        for src in self.SW_VERSIONS:
            l1_df = self._pro.index_classify(level="L1", src=src)
            if l1_df is None or l1_df.empty:
                continue
            l1_codes = l1_df["index_code"].tolist()
            logger.info(f"拉取申万行业成分({src}): {len(l1_codes)} 个一级行业")
            for l1_code in l1_codes:
                for is_new in ("Y", "N"):
                    df = self._pro.index_member_all(l1_code=l1_code, is_new=is_new)
                    time.sleep(0.2)
                    if df is not None and not df.empty:
                        frames.append(df)
        if not frames:
            return pd.DataFrame(columns=SW_MEMBER_COLS)
        result = (
            pd.concat(frames, ignore_index=True)
            .drop_duplicates(subset=["ts_code", "l3_code", "in_date"], keep="last")
            .reset_index(drop=True)
        )
        return _select_columns_or_empty(result, SW_MEMBER_COLS)

    def fetch_ci_member(self) -> pd.DataFrame:
        initial_df = self._pro.ci_index_member()
        if initial_df is None or initial_df.empty:
            return pd.DataFrame(columns=CI_MEMBER_COLS)
        l1_codes = initial_df["l1_code"].unique().tolist()
        logger.info(f"拉取中信行业成分: {len(l1_codes)} 个一级行业")
        frames = []
        for l1_code in l1_codes:
            for is_new in ("Y", "N"):
                df = self._pro.ci_index_member(l1_code=l1_code, is_new=is_new)
                time.sleep(0.2)
                if df is not None and not df.empty:
                    frames.append(df)
        if not frames:
            return pd.DataFrame(columns=CI_MEMBER_COLS)
        result = (
            pd.concat(frames, ignore_index=True)
            .drop_duplicates(subset=["ts_code", "l3_code", "in_date"], keep="last")
            .reset_index(drop=True)
        )
        return _select_columns_or_empty(result, CI_MEMBER_COLS)


def _select_columns_or_empty(df: pd.DataFrame | None, columns: list[str]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=columns)
    return df[columns]
