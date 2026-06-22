from __future__ import annotations

import importlib

import pandas as pd
from loguru import logger


class RiceQuantFetcher:
    def __init__(
        self,
        username: str = "",
        password: str = "",
        license_key: str = "",
    ):
        has_user_password = bool(username or password)
        if license_key and has_user_password:
            raise ValueError("RiceQuant credentials must use either license_key or username/password, not both")
        if not license_key and not (username and password):
            raise ValueError("RiceQuant credentials require license_key or both username and password")
        self._username = username
        self._password = password
        self._license_key = license_key
        self._rqdatac = None

    def _connect(self):
        if self._rqdatac is not None:
            return
        try:
            rqdatac = importlib.import_module("rqdatac")
        except ImportError as exc:
            raise ImportError(
                "rqdatac is required for RiceQuant sync; install it or disable [ricequant].enabled"
            ) from exc
        if self._license_key:
            rqdatac.init(username="license", password=self._license_key)
        else:
            rqdatac.init(username=self._username, password=self._password)
        self._rqdatac = rqdatac

    def fetch_stock_minute(
        self,
        order_book_ids: str | list[str],
        start_date: str,
        end_date: str,
        adjust_type: str = "none",
        skip_suspended: bool = True,
    ) -> pd.DataFrame:
        self._connect()
        logger.debug(f"拉取 RiceQuant 股票分钟线: {order_book_ids} {start_date}~{end_date}")
        df = self._rqdatac.get_price(
            order_book_ids=order_book_ids,
            start_date=start_date,
            end_date=end_date,
            frequency="1m",
            fields=None,
            adjust_type=adjust_type,
            skip_suspended=skip_suspended,
            expect_df=True,
        )
        if df is None or df.empty:
            return pd.DataFrame(columns=["order_book_id", "datetime", "trade_date"])
        result = df.reset_index()
        if "order_book_id" not in result.columns:
            if not isinstance(order_book_ids, str):
                raise ValueError("RiceQuant minute data for multiple order_book_ids must include order_book_id")
            result.insert(0, "order_book_id", order_book_ids)
        if "datetime" not in result.columns:
            raise ValueError("RiceQuant minute data must include datetime index or column")
        result["datetime"] = pd.to_datetime(result["datetime"])
        result["trade_date"] = result["datetime"].dt.strftime("%Y%m%d")
        return result

    def fetch_basic(self) -> pd.DataFrame:
        self._connect()
        logger.debug("拉取 RiceQuant 股票基础信息: all_instruments(type='CS', market='cn')")
        df = self._rqdatac.all_instruments(type="CS", market="cn")
        if df is None or df.empty:
            return pd.DataFrame(columns=["order_book_id"])
        return df.reset_index(drop=True)
