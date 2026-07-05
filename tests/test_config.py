from pathlib import Path

import pytest

from zer0share.config import load_config


VALID_TOML = """
[tushare]
token = "test_token"

[paths]
data_dir = "data"
db_path = "db/meta.duckdb"
log_path = "logs/pipeline.log"

[scheduler]
trade_cal   = "09:00"
basic       = "09:10"
daily_kline = "16:30"

[notifier]
wecom_webhook_url = "https://example.com/webhook"
enabled = false
"""


def test_load_config_returns_schedule_dict(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(VALID_TOML, encoding="utf-8")

    cfg = load_config(cfg_file)

    assert cfg.tushare_token == "test_token"
    assert cfg.data_dir == Path("data")
    assert cfg.schedule == {
        "trade_cal": "09:00",
        "basic": "09:10",
        "daily_kline": "16:30",
    }
    assert cfg.wecom_webhook_url == "https://example.com/webhook"
    assert cfg.notifier_enabled is False


def test_load_config_notifier_enabled_true(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        VALID_TOML.replace("enabled = false", "enabled = true"),
        encoding="utf-8",
    )
    cfg = load_config(cfg_file)
    assert cfg.notifier_enabled is True


def test_load_config_defaults_quality_disabled(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        """
[tushare]
token = "token"

[paths]
data_dir = "data"
db_path = "db/meta.duckdb"
log_path = "logs/pipeline.log"

[scheduler]
daily_kline = "18:00"

[notifier]
wecom_webhook_url = ""
enabled = false
""",
        encoding="utf-8",
    )

    cfg = load_config(cfg_file)

    assert cfg.quality.enabled is False
    assert cfg.quality.mode == "daily"
    assert cfg.quality.markets == ["stock", "index", "etf", "futures", "options"]
    assert cfg.quality.notify_on == ["warn", "fail"]


def test_load_config_file_not_found():
    with pytest.raises(FileNotFoundError, match="配置文件不存在"):
        load_config(Path("nonexistent/settings.toml"))


def test_load_config_missing_key(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        "[tushare]\n"
        "# token missing\n"
        "[paths]\n"
        "data_dir='data'\n"
        "db_path='db/meta.duckdb'\n"
        "log_path='logs/pipeline.log'\n"
        "[scheduler]\n"
        "trade_cal = '09:00'\n"
        "[notifier]\n"
        "wecom_webhook_url='https://x.com'\n"
        "enabled=false\n",
        encoding="utf-8",
    )
    with pytest.raises(KeyError, match="配置文件缺少必要字段"):
        load_config(cfg_file)


def test_load_config_invalid_schedule_format(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        "[tushare]\n"
        "token = 'test'\n"
        "[paths]\n"
        "data_dir='data'\n"
        "db_path='db/meta.duckdb'\n"
        "log_path='logs/pipeline.log'\n"
        "[scheduler]\n"
        "trade_cal = 'not_a_time'\n"
        "[notifier]\n"
        "wecom_webhook_url='https://x.com'\n"
        "enabled=false\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="调度时间格式错误"):
        load_config(cfg_file)


def test_load_config_out_of_range_schedule_time(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        "[tushare]\n"
        "token = 'test'\n"
        "[paths]\n"
        "data_dir='data'\n"
        "db_path='db/meta.duckdb'\n"
        "log_path='logs/pipeline.log'\n"
        "[scheduler]\n"
        "trade_cal = '25:00'\n"
        "[notifier]\n"
        "wecom_webhook_url='https://x.com'\n"
        "enabled=false\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="调度时间格式错误"):
        load_config(cfg_file)


def test_config_is_immutable(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(VALID_TOML, encoding="utf-8")
    cfg = load_config(cfg_file)
    with pytest.raises(Exception):
        cfg.tushare_token = "hacked"
