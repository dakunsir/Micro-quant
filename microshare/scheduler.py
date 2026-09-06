from __future__ import annotations

import datetime as dt
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from uuid import uuid4
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from microshare.config import load_config
from microshare.coverage import (
    STOCK_HISTORY_START_DATES,
    build_stock_history_coverage,
)
from microshare.logging import init_logger
from microshare.notifier import build_notifier
from microshare.pipeline import Pipeline
from microshare.quality.models import QualityRunOptions
from microshare.quality.reporter import QualityReporter, format_summary
from microshare.quality.runner import QualityRunner
from microshare.quality.targets import QUALITY_TARGETS
from microshare.sources import DataSources, RiceQuantFetcher, TushareFetcher
from microshare.universe import build_mainboard_microcap


POST_CLOSE_TABLES = (
    "trade_cal",
    "basic",
    "daily_kline",
    "adj_factor",
    "daily_basic",
    "stock_st",
    "suspend_d",
    "stk_limit",
)


class _LockBusyError(RuntimeError):
    pass


def _quality_tables_for_sync(table_name: str, markets: list[str]) -> tuple[str, ...]:
    target = QUALITY_TARGETS.get(table_name)
    if target is None or target.market not in markets:
        return ()
    return (target.table,)


def _run_quality(cfg, notifier, date_value: str) -> None:
    quality_cfg = cfg.quality
    if not quality_cfg.enabled:
        return
    tables = tuple(
        target.table
        for target in QUALITY_TARGETS.values()
        if target.market in quality_cfg.markets
    )
    if not tables:
        return
    try:
        options = QualityRunOptions(mode=quality_cfg.mode, tables=tables, date=date_value)
        report = QualityRunner(cfg.data_dir).run(options)
        output_dir = QualityReporter(Path("reports") / "quality").write(report)
        notify_on = set(quality_cfg.notify_on)
        should_notify = (
            ("fail" in notify_on and report.fail_count > 0)
            or ("warn" in notify_on and report.warn_count > 0)
        )
        if should_notify:
            notifier.send(f"数据质检发现问题\n{format_summary(report)}\n报告：{output_dir}")
    except Exception as exc:
        logger.error(f"quality check failed after post-close cycle: {exc}")


def run_scheduled_table(cfg, sources, notifier, table_name: str) -> None:
    """Compatibility helper for callers using the legacy per-table scheduler."""
    with Pipeline(cfg, sources, notifier) as pipeline:
        pipeline.run(table_name)

    quality_cfg = cfg.quality
    if not quality_cfg.enabled:
        return

    tables = _quality_tables_for_sync(table_name, quality_cfg.markets)
    if not tables:
        return

    try:
        options = QualityRunOptions(
            mode="daily",
            tables=tables,
            date=dt.date.today().strftime("%Y%m%d"),
        )
        report = QualityRunner(cfg.data_dir).run(options)
        output_dir = QualityReporter(Path("reports") / "quality").write(report)
        notify_on = set(quality_cfg.notify_on)
        should_notify = (
            ("fail" in notify_on and report.fail_count > 0)
            or ("warn" in notify_on and report.warn_count > 0)
        )
        if should_notify:
            notifier.send(f"数据质检发现问题\n{format_summary(report)}\n报告：{output_dir}")
    except Exception as exc:
        logger.error(f"quality check failed after {table_name}: {exc}")


def _now(tz: ZoneInfo) -> dt.datetime:
    return dt.datetime.now(tz)


def _write_state(path: Path, state: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{state['run_id']}.tmp")
    try:
        temp_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


@contextmanager
def _file_lock(path: Path) -> Iterator[None]:
    """Acquire a non-blocking process lock using only the standard library."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    locked = False
    try:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            handle.write(b"0")
            handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise _LockBusyError(str(exc)) from exc
            locked = True
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise _LockBusyError(str(exc)) from exc
            locked = True
        yield
    finally:
        if locked:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _next_trade_date(pipeline: Pipeline, current_date: str) -> str | None:
    current = dt.datetime.strptime(current_date, "%Y%m%d").date()
    end = current + dt.timedelta(days=370)
    days = pipeline.calendar.get_trading_days(
        "SSE", (current + dt.timedelta(days=1)).strftime("%Y%m%d"), end.strftime("%Y%m%d")
    )
    return days[0] if days else None


def run_post_close_cycle(cfg, sources, notifier, now: dt.datetime | None = None) -> dict[str, object] | None:
    """Refresh the stock chain and build the next effective microcap universe."""
    scheduler_cfg = cfg.scheduler
    tz = ZoneInfo(scheduler_cfg.timezone)
    run_id = uuid4().hex
    started = now or _now(tz)
    state: dict[str, object] = {
        "run_id": run_id,
        "status": "running",
        "started_at": started.isoformat(),
        "finished_at": None,
        "phases": {table: {"status": "pending"} for table in POST_CLOSE_TABLES},
        "coverage": {"status": "pending"},
        "universe": {"status": "pending"},
        "error": None,
    }
    lock_busy = False

    try:
        with _file_lock(scheduler_cfg.lock_path):
            _write_state(scheduler_cfg.state_path, state)
            with Pipeline(cfg, sources, notifier) as pipeline:
                for table_name in POST_CLOSE_TABLES:
                    state["phases"][table_name] = {"status": "running"}
                    _write_state(scheduler_cfg.state_path, state)
                    if table_name in STOCK_HISTORY_START_DATES:
                        result = pipeline.run(
                            table_name,
                            repair_missing=True,
                            repair_start_date=STOCK_HISTORY_START_DATES[table_name],
                        )
                    else:
                        result = pipeline.run(table_name)
                    phase_state: dict[str, object] = {"status": "success"}
                    if isinstance(result, dict):
                        phase_state["result"] = result
                    state["phases"][table_name] = phase_state
                    _write_state(scheduler_cfg.state_path, state)

                    if table_name == "trade_cal":
                        current_date = pipeline.calendar.today()
                        state["current_trade_date"] = current_date
                        if not pipeline.calendar.is_trading_day("SSE", current_date):
                            state["status"] = "skipped"
                            state["reason"] = "non_trading_day"
                            for remaining in POST_CLOSE_TABLES[1:]:
                                state["phases"][remaining] = {"status": "skipped"}
                            state["universe"] = {"status": "skipped"}
                            break

                if state["status"] == "running":
                    current_date = state["current_trade_date"]
                    coverage = build_stock_history_coverage(
                        cfg.data_dir,
                        end_date=current_date,
                        validate_partitions=False,
                    )
                    state["coverage"] = {
                        "status": "success" if coverage["complete"] else "failed",
                        "trade_days": coverage["trade_days"],
                        "tables": {
                            name: {
                                "missing_partitions": report["missing_partitions"],
                                "empty_partitions": report["empty_partitions"],
                                "invalid_partitions": len(report["invalid_partitions"]),
                            }
                            for name, report in coverage["tables"].items()
                        },
                        "open_t1_ready_through": coverage["open_t1_ready_through"],
                    }
                    _write_state(scheduler_cfg.state_path, state)
                    if not coverage["complete"]:
                        raise RuntimeError(
                            "stock history coverage incomplete; "
                            "universe build is blocked"
                        )
                    next_date = _next_trade_date(pipeline, current_date)
                    state["source_trade_date"] = current_date
                    state["effective_trade_date"] = next_date
                    if next_date is None:
                        state["universe"] = {
                            "status": "skipped",
                            "warning": "trade calendar has no next trading day",
                        }
                    else:
                        manifest = build_mainboard_microcap(
                            cfg.data_dir,
                            dt.datetime.strptime(next_date, "%Y%m%d").date(),
                            cfg.universe,
                        )
                        state["universe"] = {
                            "status": "success",
                            "member_count": manifest.get("member_count"),
                            "quality_status": manifest.get("quality_status"),
                            "warnings": manifest.get("warnings", []),
                        }
                    _run_quality(cfg, notifier, current_date)

            if state["status"] == "running":
                state["status"] = "success"
    except _LockBusyError as exc:
        lock_busy = True
        logger.info(f"post-close cycle skipped because another run holds the lock: {exc}")
        return None
    except Exception as exc:
        state["status"] = "failed"
        state["error"] = str(exc)
        logger.exception("post-close cycle failed: {}", exc)
        notifier.send(f"收盘后增量调度失败\n运行：{run_id}\n错误：{exc}")
    finally:
        state["finished_at"] = _now(tz).isoformat()
        if not lock_busy:
            try:
                _write_state(scheduler_cfg.state_path, state)
            except Exception as exc:
                logger.error(f"failed to write scheduler state: {exc}")
    return state


def _build_sources(cfg) -> DataSources:
    return DataSources(
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


def start_scheduler(config_path: str = "config/settings.toml") -> None:
    cfg = load_config(Path(config_path))
    init_logger(cfg.log_path)
    if not cfg.scheduler.enabled:
        logger.info("调度器未启用 (scheduler.enabled=false)")
        return

    sources = _build_sources(cfg)
    notifier = build_notifier(cfg.notifier)
    scheduler = BlockingScheduler(timezone=ZoneInfo(cfg.scheduler.timezone))

    if cfg.scheduler.run_time is not None:
        hour, minute = (int(x) for x in cfg.scheduler.run_time.split(":"))
        scheduler.add_job(
            lambda: run_post_close_cycle(cfg, sources, notifier),
            CronTrigger(
                hour=hour,
                minute=minute,
                timezone=ZoneInfo(cfg.scheduler.timezone),
            ),
            id="post_close",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )
        logger.info(f"调度器启动: 每个交易日收盘后 {cfg.scheduler.run_time} 执行股票链")
        notifier.send(
            f"调度器已启动\n收盘后股票链：{cfg.scheduler.run_time}\n配置：{config_path}"
        )
    else:
        # Compatibility for old settings files; new settings use the fixed workflow above.
        for table_name, time_str in cfg.schedule.items():
            hour, minute = (int(x) for x in time_str.split(":"))
            scheduler.add_job(
                lambda t=table_name: run_scheduled_table(cfg, sources, notifier, t),
                CronTrigger(hour=hour, minute=minute),
                id=table_name,
            )
        logger.info(f"调度器启动: {len(cfg.schedule)} 个兼容任务已调度")
        notifier.send(
            f"调度器已启动\n已调度：{len(cfg.schedule)} 个表\n配置：{config_path}"
        )

    scheduler.start()
