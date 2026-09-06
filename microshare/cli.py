import datetime as dt
from pathlib import Path

import click

from microshare.config import load_config
from microshare.logging import init_logger
from microshare.notifier import build_notifier
from microshare.pipeline import Pipeline
from microshare.quality.models import QualityRunOptions
from microshare.quality.reporter import QualityReporter, format_summary
from microshare.quality.runner import QualityRunner
from microshare.quality.targets import select_targets
from microshare.sources import DataSources, RiceQuantFetcher, TushareFetcher
from microshare.storage import MetaStore
from microshare.universe import (
    build_mainboard_microcap,
    build_mainboard_microcap_range,
    build_universes,
    build_universes_range,
)


def _validate_date(ctx, param, value):
    if value is None:
        return None
    try:
        dt.datetime.strptime(value, "%Y%m%d")
        return value
    except ValueError:
        raise click.BadParameter("格式应为 YYYYMMDD，例如 20240102")


def _parse_date(s: str):
    return dt.datetime.strptime(s, "%Y%m%d").date()


def _make_pipeline(config_path: str = "config/settings.toml") -> Pipeline:
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
    return Pipeline(cfg, sources, notifier)


@click.group()
def cli():
    pass


@cli.group("api")
def api_cmd():
    """启动只读本地数据 API。"""
    pass


@api_cmd.command("start")
@click.option("--config", "config_path", default="config/settings.toml", show_default=True)
def api_start_cmd(config_path: str) -> None:
    """启动 FastAPI/ OpenAPI 查询服务。"""
    from microshare.http_api import run_server

    run_server(config_path)


FUTURES_TABLES = [
    "fut_basic",
    "fut_daily",
    "fut_holding",
    "fut_wsr",
    "fut_settle",
    "fut_mapping",
    "ft_limit",
    "fut_weekly",
    "fut_monthly",
    "fut_index_daily",
    "fut_weekly_detail",
]

OPTIONS_TABLES = [
    "opt_basic",
    "opt_daily",
]

ETF_TABLES = [
    "fund_daily",
    "fund_adj",
    "etf_share_size",
    "etf_sh_cons",
    "etf_basic",
    "etf_index",
]

STOCK_TABLES = [
    "basic",
    "trade_cal",
    "daily_kline",
    "adj_factor",
    "daily_basic",
    "stock_st",
    "suspend_d",
    "stk_limit",
    "index_daily",
    "index_weight",
    "idx_anns",
    "industry",
    "sw_daily",
    "ci_member",
]

RICEQUANT_TABLES = [
    "ricequant_basic",
    "ricequant_stock_minute",
    "ricequant_etf_basic",
    "ricequant_etf_minute",
]

SYNC_TABLES = [
    *STOCK_TABLES,
    *FUTURES_TABLES,
    *OPTIONS_TABLES,
    *ETF_TABLES,
    *RICEQUANT_TABLES,
]


@cli.command()
@click.option(
    "--table",
    type=click.Choice(SYNC_TABLES),
    default=None,
)
@click.option("--all", "sync_all", is_flag=True, default=False)
@click.option("--stock", "sync_stock", is_flag=True, default=False)
@click.option("--futures", "sync_futures", is_flag=True, default=False)
@click.option("--options", "sync_options", is_flag=True, default=False)
@click.option("--etf", "sync_etf", is_flag=True, default=False)
@click.option("--ricequant", "sync_ricequant", is_flag=True, default=False)
@click.option("--start-date", default=None, callback=_validate_date)
@click.option("--end-date", default=None, callback=_validate_date)
def sync(
    table: str | None,
    sync_all: bool,
    sync_stock: bool,
    sync_futures: bool,
    sync_options: bool,
    sync_etf: bool,
    sync_ricequant: bool,
    start_date: str | None,
    end_date: str | None,
) -> None:
    """同步数据。"""
    if end_date is not None and start_date is None:
        raise click.UsageError("--end-date requires --start-date")
    if start_date is not None and end_date is not None and end_date < start_date:
        raise click.UsageError("--end-date must be on or after --start-date")

    with _make_pipeline() as pipeline:
        if table is not None and (start_date is not None or end_date is not None):
            job = pipeline.registry.get(table)
            if job is not None and not job.supports_date_range:
                raise click.UsageError("date range options are only supported for daily partitioned tables")

        if sync_all:
            pipeline.run_all(start_date=start_date, end_date=end_date)
        elif sync_stock:
            for t in STOCK_TABLES:
                pipeline.run(t, start_date=start_date, end_date=end_date)
        elif sync_futures:
            for t in FUTURES_TABLES:
                pipeline.run(t, start_date=start_date, end_date=end_date)
        elif sync_options:
            for t in OPTIONS_TABLES:
                pipeline.run(t, start_date=start_date, end_date=end_date)
        elif sync_etf:
            for t in ETF_TABLES:
                pipeline.run(t, start_date=start_date, end_date=end_date)
        elif sync_ricequant:
            for t in RICEQUANT_TABLES:
                pipeline.run(t, start_date=start_date, end_date=end_date)
        elif table is not None:
            pipeline.run(table, start_date=start_date, end_date=end_date)
        else:
            raise click.UsageError("需要指定 --table、--stock、--futures、--options、--etf、--ricequant 或 --all")


@cli.group()
def quality():
    """数据质检。"""


@quality.command("check")
@click.option("--table", "table_name", default=None)
@click.option(
    "--market",
    type=click.Choice(["stock", "index", "etf", "futures", "options"]),
    default=None,
)
@click.option("--all", "all_targets", is_flag=True, default=False)
@click.option(
    "--mode",
    type=click.Choice(["full", "daily"]),
    default="daily",
    show_default=True,
)
@click.option("--start-date", default=None, callback=_validate_date)
@click.option("--end-date", default=None, callback=_validate_date)
@click.option("--date", "single_date", default=None, callback=_validate_date)
def quality_check(
    table_name: str | None,
    market: str | None,
    all_targets: bool,
    mode: str,
    start_date: str | None,
    end_date: str | None,
    single_date: str | None,
) -> None:
    """检查本地 Parquet 数据质量。"""
    if mode == "full" and (start_date is None or end_date is None):
        raise click.UsageError("full mode requires --start-date and --end-date")
    if mode == "daily" and (start_date is not None or end_date is not None):
        raise click.UsageError("daily mode uses --date, not --start-date/--end-date")
    if mode == "full" and single_date is not None:
        raise click.UsageError("full mode does not use --date")

    try:
        targets = select_targets(table=table_name, market=market, all_targets=all_targets)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc

    cfg = load_config(Path("config/settings.toml"))
    options = QualityRunOptions(
        mode=mode,
        tables=tuple(target.table for target in targets),
        start_date=start_date,
        end_date=end_date,
        date=single_date,
    )
    report = QualityRunner(cfg.data_dir).run(options)
    QualityReporter(Path("reports") / "quality").write(report)
    click.echo(format_summary(report))
    if report.fail_count > 0:
        raise click.exceptions.Exit(1)


@cli.command("build-universe")
@click.option("--date", "trade_date", default=None, callback=_validate_date)
@click.option("--start-date", default=None, callback=_validate_date)
@click.option("--end-date", default=None, callback=_validate_date)
def build_universe_cmd(
    trade_date: str | None,
    start_date: str | None,
    end_date: str | None,
) -> None:
    """构建股票池。"""
    if trade_date is not None and (start_date is not None or end_date is not None):
        raise click.UsageError("--date cannot be used with --start-date or --end-date")

    cfg = load_config(Path("config/settings.toml"))
    init_logger(cfg.log_path)
    if trade_date is not None:
        counts = build_universes(cfg.data_dir, _parse_date(trade_date))
        for name, count in counts.items():
            click.echo(f"{name}: {count}")
        return

    summary = build_universes_range(
        cfg.data_dir,
        start_date=_parse_date(start_date) if start_date is not None else None,
        end_date=_parse_date(end_date) if end_date is not None else None,
    )
    click.echo(
        f"range: {summary['start_date']} ~ {summary['end_date']}, "
        f"trading_days: {summary['trading_days']}, "
        f"built: {summary['built_days']}, skipped: {summary['skipped_days']}"
    )
    for name, count in summary["counts"].items():
        click.echo(f"{name}: {count}")


@cli.command("build-mainboard-microcap")
@click.option("--date", "trade_date", default=None, callback=_validate_date)
@click.option("--start-date", default=None, callback=_validate_date)
@click.option("--end-date", default=None, callback=_validate_date)
def build_mainboard_microcap_cmd(
    trade_date: str | None,
    start_date: str | None,
    end_date: str | None,
) -> None:
    """构建按前一交易日数据筛选、下一交易日生效的主板微盘股票池。"""
    if trade_date is not None and (start_date is not None or end_date is not None):
        raise click.UsageError("--date cannot be used with --start-date or --end-date")

    cfg = load_config(Path("config/settings.toml"))
    init_logger(cfg.log_path)
    try:
        if trade_date is not None:
            manifest = build_mainboard_microcap(
                cfg.data_dir,
                _parse_date(trade_date),
                config=cfg.universe,
            )
            click.echo(
                f"{cfg.universe.name}: {manifest['member_count']} members "
                f"(source={manifest['source_trade_date']}, "
                f"effective={manifest['effective_trade_date']}, "
                f"status={manifest['quality_status']})"
            )
            for warning in manifest["warnings"]:
                click.echo(f"warning: {warning}")
            return

        summary = build_mainboard_microcap_range(
            cfg.data_dir,
            start_date=_parse_date(start_date) if start_date is not None else None,
            end_date=_parse_date(end_date) if end_date is not None else None,
            config=cfg.universe,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(
        f"range: {summary['start_date']} ~ {summary['end_date']}, "
        f"trading_days: {summary['trading_days']}, "
        f"built: {summary['built_days']}, skipped: {summary['skipped_days']}, "
        f"members: {summary['member_count']}"
    )
    for warning in summary["warnings"]:
        click.echo(f"warning: {warning}")


@cli.command()
def status() -> None:
    """显示各表最后更新时间。"""
    cfg = load_config(Path("config/settings.toml"))
    with MetaStore(cfg.db_path) as store:
        for table in SYNC_TABLES:
            last = store.get_last_date(table)
            click.echo(f"{table}: {last or '从未同步'}")


@cli.command("scheduler")
@click.argument("action", type=click.Choice(["start"]))
def scheduler_cmd(action: str) -> None:
    """启动定时调度。"""
    from microshare.scheduler import start_scheduler

    start_scheduler()
