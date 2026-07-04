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
wecom_webhook_url = "https://example.com"
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
        patch("zer0share.scheduler.Pipeline") as mock_pipeline_cls,
    ):
        mock_pipeline_cls.return_value.__enter__ = lambda s: s
        mock_pipeline_cls.return_value.__exit__ = MagicMock(return_value=False)
        from zer0share.scheduler import start_scheduler
        start_scheduler(str(cfg_file))

    assert set(registered_jobs) == {"trade_cal", "basic", "daily_kline", "adj_factor"}
    assert len(registered_jobs) == 4


def test_start_scheduler_sends_startup_notification(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(VALID_CONFIG, encoding="utf-8")
    notifier = MagicMock()

    with (
        patch("tushare.pro_api"),
        patch("zer0share.scheduler.Notifier", return_value=notifier),
        patch("apscheduler.schedulers.blocking.BlockingScheduler.start"),
        patch("apscheduler.schedulers.blocking.BlockingScheduler.add_job"),
        patch("zer0share.scheduler.Pipeline"),
    ):
        from zer0share.scheduler import start_scheduler

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
        patch("zer0share.scheduler.Pipeline") as mock_pipeline_cls,
    ):
        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.__enter__.return_value = mock_pipeline
        mock_pipeline.__exit__.return_value = False

        from zer0share.scheduler import start_scheduler

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
        patch("zer0share.scheduler.CronTrigger", side_effect=fake_cron_trigger),
        patch("apscheduler.schedulers.blocking.BlockingScheduler.start"),
        patch(
            "apscheduler.schedulers.blocking.BlockingScheduler.add_job",
            side_effect=fake_add_job,
        ),
        patch("zer0share.scheduler.Pipeline") as mock_pipeline_cls,
    ):
        mock_pipeline_cls.return_value.__enter__ = lambda s: s
        mock_pipeline_cls.return_value.__exit__ = MagicMock(return_value=False)
        from zer0share.scheduler import start_scheduler
        start_scheduler(str(cfg_file))

    assert job_cron_map["trade_cal"] == {"hour": 9, "minute": 0}
    assert job_cron_map["basic"] == {"hour": 9, "minute": 10}
    assert job_cron_map["daily_kline"] == {"hour": 16, "minute": 30}
    assert job_cron_map["adj_factor"] == {"hour": 16, "minute": 35}
