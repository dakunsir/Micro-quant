from unittest.mock import MagicMock, patch

from micro.scheduler import run_scheduled_table


def test_run_scheduled_table_runs_quality_without_raising(tmp_path):
    cfg = MagicMock()
    cfg.data_dir = tmp_path
    cfg.quality.enabled = True
    cfg.quality.mode = "daily"
    cfg.quality.markets = ["stock"]
    cfg.quality.notify_on = ["warn", "fail"]

    fetcher = MagicMock()
    notifier = MagicMock()
    report = MagicMock()
    report.warn_count = 1
    report.fail_count = 0

    with (
        patch("micro.scheduler.Pipeline") as pipeline_cls,
        patch("micro.scheduler.QualityRunner") as runner_cls,
        patch("micro.scheduler.QualityReporter") as reporter_cls,
        patch("micro.scheduler.format_summary", return_value="quality summary"),
    ):
        pipeline_cls.return_value.__enter__.return_value = pipeline_cls.return_value
        pipeline_cls.return_value.__exit__.return_value = False
        runner_cls.return_value.run.return_value = report
        reporter_cls.return_value.write.return_value = tmp_path / "reports"

        run_scheduled_table(cfg, fetcher, notifier, "daily_kline")

    pipeline_cls.return_value.run.assert_called_once_with("daily_kline")
    runner_cls.return_value.run.assert_called_once()
    reporter_cls.return_value.write.assert_called_once_with(report)
    notifier.send.assert_called()
