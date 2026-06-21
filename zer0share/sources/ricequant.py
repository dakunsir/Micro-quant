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
        try:
            rqdatac = importlib.import_module("rqdatac")
        except ImportError as exc:
            raise ImportError(
                "rqdatac is required for RiceQuant sync; install it or disable [ricequant].enabled"
            ) from exc
        has_user_password = bool(username or password)
        if license_key and has_user_password:
            raise ValueError("RiceQuant credentials must use either license_key or username/password, not both")
        if license_key:
            rqdatac.init(username="license", password=license_key)
        elif username and password:
            rqdatac.init(username=username, password=password)
        else:
            raise ValueError("RiceQuant credentials require license_key or both username and password")
        self._rqdatac = rqdatac

    def fetch_stock_minute(
        self,
        order_book_id: str,
        start_date: str,
        end_date: str,
        adjust_type: str = "none",
        skip_suspended: bool = True,
    ) -> pd.DataFrame:
        logger.debug(f"拉取 RiceQuant 股票分钟线: {order_book_id} {start_date}~{end_date}")
        df = self._rqdatac.get_price(
            order_book_ids=order_book_id,
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
            result.insert(0, "order_book_id", order_book_id)
        if "datetime" not in result.columns:
            raise ValueError("RiceQuant minute data must include datetime index or column")
        result["datetime"] = pd.to_datetime(result["datetime"])
        result["trade_date"] = result["datetime"].dt.strftime("%Y%m%d")
        return result

    def fetch_basic(self) -> pd.DataFrame:
        logger.debug("拉取 RiceQuant 股票基础信息: all_instruments(type='CS', market='cn')")
        df = self._rqdatac.all_instruments(type="CS", market="cn")
        if df is None or df.empty:
            return pd.DataFrame(columns=["order_book_id"])
        return df.reset_index(drop=True)
