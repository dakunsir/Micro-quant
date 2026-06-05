from datetime import date
from loguru import logger

from zer0share.storage import write_sw_classify, write_sw_member, write_ci_member
from zer0share.sync import SyncContext
from zer0share.sync._helpers import skip_if_not_trading


def sync_industry(ctx: SyncContext) -> None:
    if skip_if_not_trading(ctx, "SSE"):
        return
    today = date.today()
    try:
        df = ctx.fetcher.fetch_sw_classify()
        write_sw_classify(ctx.cfg.data_dir, df)
        ctx.meta.update_last_date("sw_classify", today)
        logger.info(f"sw_classify 同步完成: {len(df)} 条")

        df = ctx.fetcher.fetch_sw_member()
        write_sw_member(ctx.cfg.data_dir, df)
        ctx.meta.update_last_date("sw_member", today)
        logger.info(f"sw_member 同步完成: {len(df)} 条")
    except Exception as e:
        logger.error(f"industry 同步失败: {e}")
        ctx.notifier.send(f"industry 同步失败: {e}")
        raise


def sync_ci_member(ctx: SyncContext) -> None:
    if skip_if_not_trading(ctx, "SSE"):
        return
    today = date.today()
    try:
        df = ctx.fetcher.fetch_ci_member()
        write_ci_member(ctx.cfg.data_dir, df)
        ctx.meta.update_last_date("ci_member", today)
        logger.info(f"ci_member 同步完成: {len(df)} 条")
    except Exception as e:
        logger.error(f"ci_member 同步失败: {e}")
        ctx.notifier.send(f"ci_member 同步失败: {e}")
        raise
