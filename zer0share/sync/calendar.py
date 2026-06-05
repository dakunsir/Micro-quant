import pandas as pd
from datetime import date, timedelta
from loguru import logger

from zer0share.storage import read_trade_cal, write_trade_cal
from zer0share.sync import SyncContext
from zer0share.sync._helpers import (
    ALL_EXCHANGES, TRADE_CAL_FIRST_DATE, parse_tushare_date,
)


def _merge_trade_cal(existing: pd.DataFrame, fetched: pd.DataFrame) -> pd.DataFrame:
    if existing.empty:
        return fetched
    if fetched.empty:
        return existing
    return (
        pd.concat([existing, fetched], ignore_index=True)
        .drop_duplicates(subset=["exchange", "cal_date"], keep="last")
        .sort_values(["exchange", "cal_date"])
        .reset_index(drop=True)
    )


def sync_trade_cal(ctx: SyncContext) -> None:
    try:
        end = date(date.today().year, 12, 31)
        max_dates: list[date] = []
        for exchange in ALL_EXCHANGES:
            existing = read_trade_cal(ctx.cfg.data_dir, exchange)
            last = (
                parse_tushare_date(existing["cal_date"].max())
                if not existing.empty
                else None
            )
            start = (last + timedelta(days=1)) if last else TRADE_CAL_FIRST_DATE

            if start <= end:
                fetched = ctx.fetcher.fetch_trade_cal(exchange, start, end)
                df = _merge_trade_cal(existing, fetched)
                write_trade_cal(ctx.cfg.data_dir, exchange, df)
                logger.info(
                    f"trade_cal {exchange} 写入完成: 新增 {len(fetched)} 条, "
                    f"共 {len(df)} 条"
                )
            else:
                df = existing
                logger.info(f"trade_cal {exchange} 已覆盖到 {last}，无需同步")

            if not df.empty:
                max_dates.append(parse_tushare_date(df["cal_date"].max()))

        ctx.meta.load_trade_cal_from_parquet(ctx.cfg.data_dir, ALL_EXCHANGES)
        if max_dates:
            ctx.meta.update_last_date("trade_cal", min(max_dates))
        logger.info("trade_cal 全部同步完成")
    except Exception as e:
        logger.error(f"trade_cal 同步失败: {e}")
        ctx.notifier.send(f"trade_cal 同步失败: {e}")
        raise
