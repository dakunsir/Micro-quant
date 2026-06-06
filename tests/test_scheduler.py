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


def test_start_scheduler_uses_correct_cron_times(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(VALID_CONFIG, encoding="utf-8")

    cron_calls = []

    def fake_cron_trigger(**kwargs):
        cron_calls.append(kwargs)
        return MagicMock()

    with (
        patch("tushare.pro_api"),
        patch("zer0share.scheduler.CronTrigger", side_effect=fake_cron_trigger),
        patch("apscheduler.schedulers.blocking.BlockingScheduler.start"),
        patch("apscheduler.schedulers.blocking.BlockingScheduler.add_job"),
        patch("zer0share.scheduler.Pipeline") as mock_pipeline_cls,
    ):
        mock_pipeline_cls.return_value.__enter__ = lambda s: s
        mock_pipeline_cls.return_value.__exit__ = MagicMock(return_value=False)
        from zer0share.scheduler import start_scheduler
        start_scheduler(str(cfg_file))

    assert cron_calls[0] == {"hour": 9, "minute": 0}   # trade_cal = "09:00"
    assert cron_calls[1] == {"hour": 9, "minute": 10}  # basic = "09:10"
    assert cron_calls[2] == {"hour": 16, "minute": 30} # daily_kline = "16:30"
    assert cron_calls[3] == {"hour": 16, "minute": 35} # adj_factor = "16:35"
