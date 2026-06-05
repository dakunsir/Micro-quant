import time
from datetime import date
from loguru import logger

import pandas as pd

from zer0share.storage import write_opt_basic
from zer0share.sync import SyncContext
from zer0share.sync._helpers import skip_if_not_trading, sync_daily_partitioned
from zer0share.fetcher import OPTIONS_EXCHANGES


def sync_opt_basic(ctx: SyncContext) -> None:
    if skip_if_not_trading(ctx, "SSE"):
        return
    today = date.today()
    options_dir = ctx.cfg.data_dir / "options"
    all_frames = []
    try:
        for exchange in OPTIONS_EXCHANGES:
            df = ctx.fetcher.fetch_opt_basic(exchange)
            time.sleep(0.2)
            if not df.empty:
                all_frames.append(df)
        combined = pd.concat(all_frames, ignore_index=True) if all_frames else pd.DataFrame()
        write_opt_basic(options_dir, combined)
        ctx.meta.update_last_date("opt_basic", today)
        logger.info(f"opt_basic 同步完成: {len(combined)} 条")
    except Exception as e:
        logger.error(f"opt_basic 同步失败: {e}")
        ctx.notifier.send(f"opt_basic 同步失败: {e}")
        raise


def sync_opt_daily(ctx: SyncContext, start_date: date | None = None, end_date: date | None = None) -> None:
    sync_daily_partitioned(
        ctx, "opt_daily", ctx.fetcher.fetch_opt_daily, start_date, end_date,
        data_dir=ctx.cfg.data_dir / "options",
    )
