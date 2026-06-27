from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from zer0share.config import load_config
from zer0share.fetcher import TushareFetcher
from zer0share.logging import init_logger
from zer0share.notifier import Notifier
from zer0share.pipeline import Pipeline


def start_scheduler(config_path: str = "config/settings.toml") -> None:
    cfg = load_config(Path(config_path))
    init_logger(cfg.log_path)

    fetcher = TushareFetcher(cfg.tushare_token)
    notifier = Notifier(cfg.wecom_webhook_url, cfg.notifier_enabled)

    def run_table(table_name: str) -> None:
        with Pipeline(cfg, fetcher, notifier) as pipeline:
            pipeline.run(table_name)

    scheduler = BlockingScheduler()
    for table_name, time_str in cfg.schedule.items():
        hour, minute = (int(x) for x in time_str.split(":"))
        scheduler.add_job(
            lambda t=table_name: run_table(t),
            CronTrigger(hour=hour, minute=minute),
            id=table_name,
        )
    table_count = len(cfg.schedule)
    logger.info(f"调度器启动: {table_count} 个表已调度")
    scheduler.start()
