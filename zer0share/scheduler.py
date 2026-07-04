from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from zer0share.config import load_config
from zer0share.logging import init_logger
from zer0share.notifier import build_notifier
from zer0share.pipeline import Pipeline
from zer0share.sources import DataSources, RiceQuantFetcher, TushareFetcher


def start_scheduler(config_path: str = "config/settings.toml") -> None:
    cfg = load_config(Path(config_path))
    init_logger(cfg.log_path)

    sources = DataSources(
        tushare=TushareFetcher(cfg.tushare_token),
        ricequant=(
            RiceQuantFetcher(
                username=cfg.ricequant.username,
                password=cfg.ricequant.password,
                license_key=cfg.ricequant.license_key,
            )
            if cfg.ricequant.enabled
            else None
        ),
    )
    notifier = build_notifier(cfg.notifier)

    def run_table(table_name: str) -> None:
        with Pipeline(cfg, sources, notifier) as pipeline:
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
