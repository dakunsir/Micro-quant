from unittest.mock import MagicMock, patch


VALID_CONFIG = """
[tushare]
token = "test"

[paths]
data_dir = "data"
db_path = "db/meta.duckdb"
log_path = "logs/pipeline.log"

[scheduler]
trade_cal   = "09:00"
basic       = "09:10"
daily_kline = "16:30"
adj_factor  = "16:35"

[notifier]
enabled = false
"""


def test_start_scheduler_registers_all_configured_jobs(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(VALID_CONFIG, encoding="utf-8")

    registered_jobs = []

    def fake_add_job(func, trigger, id=None, **kwargs):
        registered_jobs.append(id)

    with (
        patch("tushare.pro_api"),
        patch("apscheduler.schedulers.blocking.BlockingScheduler.start"),
        patch(
            "apscheduler.schedulers.blocking.BlockingScheduler.add_job",
            side_effect=fake_add_job,
        ),
        patch("microshare.scheduler.Pipeline") as mock_pipeline_cls,
    ):
        mock_pipeline_cls.return_value.__enter__ = lambda s: s
        mock_pipeline_cls.return_value.__exit__ = MagicMock(return_value=False)
        from microshare.scheduler import start_scheduler
        start_scheduler(str(cfg_file))

    assert set(registered_jobs) == {"trade_cal", "basic", "daily_kline", "adj_factor"}
    assert len(registered_jobs) == 4


def test_start_scheduler_sends_startup_notification(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(VALID_CONFIG, encoding="utf-8")
    notifier = MagicMock()

    with (
        patch("tushare.pro_api"),
        patch("microshare.scheduler.build_notifier", return_value=notifier),
        patch("apscheduler.schedulers.blocking.BlockingScheduler.start"),
        patch("apscheduler.schedulers.blocking.BlockingScheduler.add_job"),
        patch("microshare.scheduler.Pipeline"),
    ):
        from microshare.scheduler import start_scheduler

        start_scheduler(str(cfg_file))

    notifier.send.assert_called_once()
    message = notifier.send.call_args[0][0]
    assert "调度器已启动" in message
    assert "已调度：4 个表" in message
    assert str(cfg_file) in message


def test_start_scheduler_opens_pipeline_only_when_job_runs(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(VALID_CONFIG, encoding="utf-8")

    registered_jobs = {}

    def fake_add_job(func, trigger, id=None, **kwargs):
        registered_jobs[id] = func

    with (
        patch("tushare.pro_api"),
        patch("apscheduler.schedulers.blocking.BlockingScheduler.start"),
        patch(
            "apscheduler.schedulers.blocking.BlockingScheduler.add_job",
            side_effect=fake_add_job,
        ),
        patch("microshare.scheduler.Pipeline") as mock_pipeline_cls,
    ):
        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.__enter__.return_value = mock_pipeline
        mock_pipeline.__exit__.return_value = False

        from microshare.scheduler import start_scheduler

        start_scheduler(str(cfg_file))

        mock_pipeline_cls.assert_not_called()

        registered_jobs["basic"]()

    mock_pipeline_cls.assert_called_once()
    mock_pipeline.run.assert_called_once_with("basic")
    mock_pipeline.__exit__.assert_called_once()


def test_start_scheduler_uses_correct_cron_times(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(VALID_CONFIG, encoding="utf-8")

    job_cron_map = {}  # id → {"hour": ..., "minute": ...}
    last_cron_kwargs = {}

    def fake_cron_trigger(**kwargs):
        last_cron_kwargs.update(kwargs)
        return MagicMock()

    def fake_add_job(func, trigger, id=None, **kwargs):
        job_cron_map[id] = dict(last_cron_kwargs)
        last_cron_kwargs.clear()

    with (
        patch("tushare.pro_api"),
        patch("microshare.scheduler.CronTrigger", side_effect=fake_cron_trigger),
        patch("apscheduler.schedulers.blocking.BlockingScheduler.start"),
        patch(
            "apscheduler.schedulers.blocking.BlockingScheduler.add_job",
            side_effect=fake_add_job,
        ),
        patch("microshare.scheduler.Pipeline") as mock_pipeline_cls,
    ):
        mock_pipeline_cls.return_value.__enter__ = lambda s: s
        mock_pipeline_cls.return_value.__exit__ = MagicMock(return_value=False)
        from microshare.scheduler import start_scheduler
        start_scheduler(str(cfg_file))

    assert job_cron_map["trade_cal"] == {"hour": 9, "minute": 0}
    assert job_cron_map["basic"] == {"hour": 9, "minute": 10}
    assert job_cron_map["daily_kline"] == {"hour": 16, "minute": 30}
    assert job_cron_map["adj_factor"] == {"hour": 16, "minute": 35}


FIXED_CONFIG = """
[tushare]
token = "test"

[paths]
data_dir = "data"
db_path = "db/meta.duckdb"
log_path = "logs/pipeline.log"

[api]
host = "127.0.0.1"
port = 8787
default_limit = 1000
max_limit = 5000

[scheduler]
enabled = true
timezone = "Asia/Shanghai"
run_time = "18:30"
state_path = "{state_path}"
lock_path = "{lock_path}"

[notifier]
enabled = false
"""


def test_fixed_scheduler_registers_one_post_close_job(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        FIXED_CONFIG.format(
            state_path=(tmp_path / "latest.json").as_posix(),
            lock_path=(tmp_path / "run.lock").as_posix(),
        ),
        encoding="utf-8",
    )
    scheduler = MagicMock()

    with (
        patch("microshare.scheduler.BlockingScheduler", return_value=scheduler),
        patch("microshare.scheduler.CronTrigger") as cron_cls,
        patch("microshare.scheduler._build_sources"),
        patch("microshare.scheduler.build_notifier", return_value=MagicMock()),
    ):
        from microshare.scheduler import start_scheduler

        start_scheduler(str(cfg_file))

    scheduler.add_job.assert_called_once()
    assert scheduler.add_job.call_args.kwargs["id"] == "post_close"
    assert scheduler.add_job.call_args.kwargs["max_instances"] == 1
    assert scheduler.add_job.call_args.kwargs["coalesce"] is True
    assert cron_cls.call_args.kwargs["hour"] == 18
    assert cron_cls.call_args.kwargs["minute"] == 30
    assert cron_cls.call_args.kwargs["timezone"].key == "Asia/Shanghai"
    scheduler.start.assert_called_once()


def test_post_close_cycle_runs_stock_chain_and_builds_next_day(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        FIXED_CONFIG.format(
            state_path=(tmp_path / "latest.json").as_posix(),
            lock_path=(tmp_path / "run.lock").as_posix(),
        ),
        encoding="utf-8",
    )
    from microshare.config import load_config
    from microshare.scheduler import run_post_close_cycle

    cfg = load_config(cfg_file)
    notifier = MagicMock()
    pipeline = MagicMock()
    pipeline.__enter__.return_value = pipeline
    pipeline.__exit__.return_value = False
    pipeline.calendar.today.return_value = "20240906"
    pipeline.calendar.is_trading_day.return_value = True
    pipeline.calendar.get_trading_days.return_value = ["20240909"]
    calls = []
    pipeline.run.side_effect = lambda *args, **kwargs: calls.append((args, kwargs)) or {"table": args[0]}

    with (
        patch("microshare.scheduler.Pipeline", return_value=pipeline),
        patch(
            "microshare.scheduler.build_mainboard_microcap",
            return_value={"member_count": 1000, "quality_status": "OK", "warnings": []},
        ) as build,
        patch(
            "microshare.scheduler.build_stock_history_coverage",
            return_value={
                "complete": True,
                "trade_days": 2,
                "open_t1_ready_through": "20240906",
                "tables": {
                    name: {
                        "missing_partitions": 0,
                        "empty_partitions": 0,
                        "invalid_partitions": {},
                    }
                    for name in (
                        "daily_kline", "adj_factor", "daily_basic",
                        "stock_st", "suspend_d", "stk_limit",
                    )
                },
            },
        )
    ):
        state = run_post_close_cycle(cfg, MagicMock(), notifier)

    assert state["status"] == "success"
    assert [call[0][0] for call in calls] == [
        "trade_cal", "basic", "daily_kline", "adj_factor", "daily_basic",
        "stock_st", "suspend_d", "stk_limit",
    ]
    assert calls[2][1]["repair_missing"] is True
    assert calls[2][1]["repair_start_date"] == "20150101"
    assert calls[4][1]["repair_start_date"] == "20151231"
    assert calls[6][1]["repair_start_date"] == "20150101"
    assert state["coverage"]["status"] == "success"
    build.assert_called_once()
    assert state["effective_trade_date"] == "20240909"


def test_post_close_cycle_skips_non_trading_day(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        FIXED_CONFIG.format(
            state_path=(tmp_path / "latest.json").as_posix(),
            lock_path=(tmp_path / "run.lock").as_posix(),
        ),
        encoding="utf-8",
    )
    from microshare.config import load_config
    from microshare.scheduler import run_post_close_cycle

    cfg = load_config(cfg_file)
    pipeline = MagicMock()
    pipeline.__enter__.return_value = pipeline
    pipeline.__exit__.return_value = False
    pipeline.calendar.today.return_value = "20240907"
    pipeline.calendar.is_trading_day.return_value = False

    with patch("microshare.scheduler.Pipeline", return_value=pipeline):
        state = run_post_close_cycle(cfg, MagicMock(), MagicMock())

    assert state["status"] == "skipped"
    assert state["reason"] == "non_trading_day"
    assert [call.args[0] for call in pipeline.run.call_args_list] == ["trade_cal"]
    assert state["universe"]["status"] == "skipped"


def test_post_close_cycle_records_failure_and_does_not_build_universe(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        FIXED_CONFIG.format(
            state_path=(tmp_path / "latest.json").as_posix(),
            lock_path=(tmp_path / "run.lock").as_posix(),
        ),
        encoding="utf-8",
    )
    from microshare.config import load_config
    from microshare.scheduler import run_post_close_cycle

    cfg = load_config(cfg_file)
    notifier = MagicMock()
    pipeline = MagicMock()
    pipeline.__enter__.return_value = pipeline
    pipeline.__exit__.return_value = False
    pipeline.calendar.today.return_value = "20240906"
    pipeline.calendar.is_trading_day.return_value = True
    pipeline.run.side_effect = [None, RuntimeError("daily_kline unavailable")]

    with (
        patch("microshare.scheduler.Pipeline", return_value=pipeline),
        patch("microshare.scheduler.build_mainboard_microcap") as build,
    ):
        state = run_post_close_cycle(cfg, MagicMock(), notifier)

    assert state["status"] == "failed"
    assert "daily_kline unavailable" in state["error"]
    assert state["universe"]["status"] == "pending"
    build.assert_not_called()
    notifier.send.assert_called_once()
