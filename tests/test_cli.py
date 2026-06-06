from datetime import date
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from zer0share.cli import cli


def _make_mock_pipeline(supports_date_range_for=None):
    """Return a MagicMock pipeline.

    supports_date_range_for: set of table names that support date range.
    All others return a job with supports_date_range=False.
    If None, all tables return supports_date_range=True (default MagicMock truthy).
    """
    pipeline = MagicMock()
    pipeline.__enter__.return_value = pipeline
    pipeline.__exit__.return_value = False

    if supports_date_range_for is not None:
        def fake_registry_get(table):
            job = MagicMock()
            job.supports_date_range = table in supports_date_range_for
            return job
        pipeline.registry.get.side_effect = fake_registry_get

    return pipeline


def test_sync_daily_kline_accepts_date_range():
    runner = CliRunner()
    pipeline = _make_mock_pipeline()

    with patch("zer0share.cli._make_pipeline", return_value=pipeline):
        result = runner.invoke(
            cli,
            [
                "sync",
                "--table",
                "daily_kline",
                "--start-date",
                "20160101",
                "--end-date",
                "20160131",
            ],
        )

    assert result.exit_code == 0
    pipeline.run.assert_called_once_with(
        "daily_kline",
        start_date="20160101",
        end_date="20160131",
    )


def test_sync_end_date_requires_start_date():
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["sync", "--table", "daily_kline", "--end-date", "20160131"],
    )

    assert result.exit_code != 0
    assert "--end-date requires --start-date" in result.output


def test_build_universe_accepts_date_range(tmp_path):
    runner = CliRunner()
    cfg = MagicMock()
    cfg.data_dir = "data"
    cfg.log_path = tmp_path / "pipeline.log"

    with (
        patch("zer0share.cli.load_config", return_value=cfg),
        patch("zer0share.cli.build_universes_range") as mock_build_range,
    ):
        mock_build_range.return_value = {
            "start_date": date(2024, 1, 1),
            "end_date": date(2024, 1, 31),
            "trading_days": 22,
            "built_days": 20,
            "skipped_days": 2,
            "counts": {"univ_trade_base": 100},
        }
        result = runner.invoke(
            cli,
            [
                "build-universe",
                "--start-date",
                "20240101",
                "--end-date",
                "20240131",
            ],
        )

    assert result.exit_code == 0
    mock_build_range.assert_called_once_with(
        "data",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
    )
    assert "built: 20, skipped: 2" in result.output


def test_build_universe_rejects_date_with_range():
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "build-universe",
            "--date",
            "20240131",
            "--start-date",
            "20240101",
        ],
    )

    assert result.exit_code != 0
    assert "--date cannot be used with --start-date or --end-date" in result.output


def test_sync_industry_calls_pipeline():
    runner = CliRunner()
    pipeline = _make_mock_pipeline()

    with patch("zer0share.cli._make_pipeline", return_value=pipeline):
        result = runner.invoke(cli, ["sync", "--table", "industry"])

    assert result.exit_code == 0
    pipeline.run.assert_called_once_with("industry", start_date=None, end_date=None)


def test_sync_ci_member_calls_pipeline():
    runner = CliRunner()
    pipeline = _make_mock_pipeline()

    with patch("zer0share.cli._make_pipeline", return_value=pipeline):
        result = runner.invoke(cli, ["sync", "--table", "ci_member"])

    assert result.exit_code == 0
    pipeline.run.assert_called_once_with("ci_member", start_date=None, end_date=None)


def test_sync_all_includes_industry_and_ci_member():
    runner = CliRunner()
    pipeline = _make_mock_pipeline()

    with patch("zer0share.cli._make_pipeline", return_value=pipeline):
        result = runner.invoke(cli, ["sync", "--all"])

    assert result.exit_code == 0
    pipeline.run_all.assert_called_once_with(start_date=None, end_date=None)


def test_sync_industry_rejects_date_range():
    runner = CliRunner()
    # industry does not support date range
    pipeline = _make_mock_pipeline(supports_date_range_for=set())

    with patch("zer0share.cli._make_pipeline", return_value=pipeline):
        result = runner.invoke(
            cli, ["sync", "--table", "industry", "--start-date", "20240101"]
        )

    assert result.exit_code != 0
    assert "date range options" in result.output


def test_sync_index_daily_accepts_date_range():
    runner = CliRunner()
    pipeline = _make_mock_pipeline()

    with patch("zer0share.cli._make_pipeline", return_value=pipeline):
        result = runner.invoke(
            cli,
            [
                "sync",
                "--table",
                "index_daily",
                "--start-date",
                "20240101",
                "--end-date",
                "20240131",
            ],
        )

    assert result.exit_code == 0
    pipeline.run.assert_called_once_with(
        "index_daily",
        start_date="20240101",
        end_date="20240131",
    )


def test_sync_all_includes_index_daily():
    runner = CliRunner()
    pipeline = _make_mock_pipeline()

    with patch("zer0share.cli._make_pipeline", return_value=pipeline):
        result = runner.invoke(cli, ["sync", "--all"])

    assert result.exit_code == 0
    pipeline.run_all.assert_called_once_with(start_date=None, end_date=None)


def test_sync_fut_basic_calls_pipeline():
    runner = CliRunner()
    pipeline = _make_mock_pipeline()

    with patch("zer0share.cli._make_pipeline", return_value=pipeline):
        result = runner.invoke(cli, ["sync", "--table", "fut_basic"])

    assert result.exit_code == 0
    pipeline.run.assert_called_once_with("fut_basic", start_date=None, end_date=None)


def test_sync_fut_daily_accepts_date_range():
    runner = CliRunner()
    pipeline = _make_mock_pipeline()

    with patch("zer0share.cli._make_pipeline", return_value=pipeline):
        result = runner.invoke(
            cli,
            [
                "sync",
                "--table",
                "fut_daily",
                "--start-date",
                "20240101",
                "--end-date",
                "20240131",
            ],
        )

    assert result.exit_code == 0
    pipeline.run.assert_called_once_with(
        "fut_daily",
        start_date="20240101",
        end_date="20240131",
    )


def test_sync_fut_basic_rejects_date_range():
    runner = CliRunner()
    # fut_basic does not support date range
    pipeline = _make_mock_pipeline(supports_date_range_for=set())

    with patch("zer0share.cli._make_pipeline", return_value=pipeline):
        result = runner.invoke(
            cli, ["sync", "--table", "fut_basic", "--start-date", "20240101"]
        )

    assert result.exit_code != 0
    assert "date range options" in result.output


def test_sync_all_includes_futures_tables():
    runner = CliRunner()
    pipeline = _make_mock_pipeline()

    with patch("zer0share.cli._make_pipeline", return_value=pipeline):
        result = runner.invoke(cli, ["sync", "--all"])

    assert result.exit_code == 0
    pipeline.run_all.assert_called_once_with(start_date=None, end_date=None)


def test_sync_ft_limit_accepts_date_range():
    runner = CliRunner()
    pipeline = _make_mock_pipeline()

    with patch("zer0share.cli._make_pipeline", return_value=pipeline):
        result = runner.invoke(
            cli,
            [
                "sync",
                "--table",
                "ft_limit",
                "--start-date",
                "20240101",
                "--end-date",
                "20240131",
            ],
        )

    assert result.exit_code == 0
    pipeline.run.assert_called_once_with(
        "ft_limit",
        start_date="20240101",
        end_date="20240131",
    )


def test_sync_fut_weekly_detail_accepts_date_range():
    runner = CliRunner()
    pipeline = _make_mock_pipeline()

    with patch("zer0share.cli._make_pipeline", return_value=pipeline):
        result = runner.invoke(
            cli,
            [
                "sync",
                "--table",
                "fut_weekly_detail",
                "--start-date",
                "20240101",
                "--end-date",
                "20240131",
            ],
        )

    assert result.exit_code == 0
    pipeline.run.assert_called_once_with(
        "fut_weekly_detail",
        start_date="20240101",
        end_date="20240131",
    )


def test_sync_all_includes_futures_batch2_tables():
    runner = CliRunner()
    pipeline = _make_mock_pipeline()

    with patch("zer0share.cli._make_pipeline", return_value=pipeline):
        result = runner.invoke(cli, ["sync", "--all"])

    assert result.exit_code == 0
    pipeline.run_all.assert_called_once_with(start_date=None, end_date=None)


def test_sync_opt_basic_calls_pipeline():
    runner = CliRunner()
    pipeline = _make_mock_pipeline()

    with patch("zer0share.cli._make_pipeline", return_value=pipeline):
        result = runner.invoke(cli, ["sync", "--table", "opt_basic"])

    assert result.exit_code == 0
    pipeline.run.assert_called_once_with("opt_basic", start_date=None, end_date=None)


def test_sync_opt_daily_accepts_date_range():
    runner = CliRunner()
    pipeline = _make_mock_pipeline()

    with patch("zer0share.cli._make_pipeline", return_value=pipeline):
        result = runner.invoke(
            cli,
            ["sync", "--table", "opt_daily", "--start-date", "20240101", "--end-date", "20240131"],
        )

    assert result.exit_code == 0
    pipeline.run.assert_called_once_with(
        "opt_daily",
        start_date="20240101",
        end_date="20240131",
    )


def test_sync_opt_basic_rejects_date_range():
    runner = CliRunner()
    # opt_basic does not support date range
    pipeline = _make_mock_pipeline(supports_date_range_for=set())

    with patch("zer0share.cli._make_pipeline", return_value=pipeline):
        result = runner.invoke(
            cli, ["sync", "--table", "opt_basic", "--start-date", "20240101"]
        )

    assert result.exit_code != 0
    assert "date range options" in result.output


def test_sync_all_includes_options_tables():
    runner = CliRunner()
    pipeline = _make_mock_pipeline()

    with patch("zer0share.cli._make_pipeline", return_value=pipeline):
        result = runner.invoke(cli, ["sync", "--all"])

    assert result.exit_code == 0
    pipeline.run_all.assert_called_once_with(start_date=None, end_date=None)
