# Backward-compat shim — will be removed in Task 10
# Import the real constants/functions from their new homes
from zer0share.sync._jobs import FIRST_DATE  # noqa: F401

TRADE_CAL_FIRST_DATE = "19900101"
PROGRESS_INTERVAL = 50
EXCHANGES = ["SSE", "SZSE"]
ALL_EXCHANGES = ["SSE", "SZSE", "CFFEX", "DCE", "SHFE", "CZCE", "INE", "GFEX"]
INDEX_CODES = ["399300.SZ", "000905.SH", "000852.SH"]


def skip_if_not_trading(ctx, exchange: str) -> bool:
    return ctx.calendar.skip_if_not_trading(exchange)


def ensure_trade_cal_loaded(ctx) -> None:
    ctx.calendar.ensure_loaded(ctx)
