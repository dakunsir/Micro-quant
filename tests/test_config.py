from pathlib import Path

import pytest

from microshare.config import load_config


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
enabled = false

[notifier.feishu]
enabled = false
receive_id_type = "user_id"
receive_id = ""
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
    assert cfg.notifier.enabled is False
    assert cfg.notifier.feishu.receive_id_type == "user_id"
    assert cfg.notifier.feishu.receive_id == ""
    assert cfg.notifier.feishu.enabled is False


def test_load_config_notifier_enabled_true(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        VALID_TOML.replace(
            "[notifier]\nenabled = false",
            "[notifier]\nenabled = true",
        ).replace('receive_id = ""', 'receive_id = "fd6a7g21"')
        .replace('[notifier.feishu]\nenabled = false', '[notifier.feishu]\nenabled = true'),
        encoding="utf-8",
    )
    cfg = load_config(cfg_file)
    assert cfg.notifier.enabled is True
    assert cfg.notifier.feishu.enabled is True


def test_load_config_rejects_legacy_wecom_notifier(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        """
[tushare]
token = "test_token"

[paths]
data_dir = "data"
db_path = "db/meta.duckdb"
log_path = "logs/pipeline.log"

[scheduler]
daily_kline = "16:30"

[notifier]
enabled = true

[notifier.wecom]
enabled = true
webhook_url = "https://example.com/wecom"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="已移除或不支持"):
        load_config(cfg_file)


def test_load_config_rejects_legacy_wecom_when_disabled(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        """
[tushare]
token = "test_token"

[paths]
data_dir = "data"
db_path = "db/meta.duckdb"
log_path = "logs/pipeline.log"

[scheduler]
daily_kline = "16:30"

[notifier]
enabled = true

[notifier.wecom]
enabled = false
webhook_url = "https://example.com/wecom"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="已移除或不支持"):
        load_config(cfg_file)


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


def test_load_config_defaults_ricequant_disabled(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(VALID_TOML, encoding="utf-8")

    cfg = load_config(cfg_file)

    assert cfg.ricequant.enabled is False
    assert cfg.ricequant.username == ""
    assert cfg.ricequant.password == ""
    assert cfg.ricequant.license_key == ""
    assert cfg.ricequant.stock_minute.request_sleep_seconds == 0.2
    assert cfg.ricequant.stock_minute.batch_size == 1000
    assert cfg.ricequant.stock_minute.adjust_type == "none"
    assert cfg.ricequant.stock_minute.skip_suspended is True


def test_load_config_parses_ricequant_section(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        VALID_TOML
        + """

[ricequant]
enabled = true
username = "rq_user"
password = "rq_password"
license_key = ""

[ricequant.stock_minute]
request_sleep_seconds = 0.5
batch_size = 500
adjust_type = "none"
skip_suspended = false
""",
        encoding="utf-8",
    )

    cfg = load_config(cfg_file)

    assert cfg.ricequant.enabled is True
    assert cfg.ricequant.username == "rq_user"
    assert cfg.ricequant.password == "rq_password"
    assert cfg.ricequant.license_key == ""
    assert cfg.ricequant.stock_minute.request_sleep_seconds == 0.5
    assert cfg.ricequant.stock_minute.batch_size == 500
    assert cfg.ricequant.stock_minute.adjust_type == "none"
    assert cfg.ricequant.stock_minute.skip_suspended is False


def test_load_config_parses_ricequant_license_key(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        VALID_TOML
        + """

[ricequant]
enabled = true
license_key = "rq_license_key"
""",
        encoding="utf-8",
    )

    cfg = load_config(cfg_file)

    assert cfg.ricequant.enabled is True
    assert cfg.ricequant.username == ""
    assert cfg.ricequant.password == ""
    assert cfg.ricequant.license_key == "rq_license_key"


def test_load_config_rejects_ambiguous_ricequant_credentials(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        VALID_TOML
        + """

[ricequant]
enabled = true
username = "rq_user"
password = "rq_password"
license_key = "rq_license_key"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="ricequant credentials"):
        load_config(cfg_file)


def test_load_config_rejects_enabled_ricequant_without_credentials(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        VALID_TOML
        + """

[ricequant]
enabled = true
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="ricequant credentials"):
        load_config(cfg_file)


def test_load_config_rejects_unsupported_ricequant_adjust_type(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        VALID_TOML
        + """

[ricequant]
enabled = true
username = "rq_user"
password = "rq_password"

[ricequant.stock_minute]
adjust_type = "pre"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="ricequant.stock_minute.adjust_type"):
        load_config(cfg_file)


def test_load_config_parses_feishu_notifier_section(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        VALID_TOML.replace('[notifier.feishu]\nenabled = false\nreceive_id_type = "user_id"\nreceive_id = ""',
                          '[notifier.feishu]\nenabled = true\nreceive_id_type = "user_id"\nreceive_id = "fd6a7g21"'),
        encoding="utf-8",
    )
    cfg = load_config(cfg_file)
    assert cfg.notifier.enabled is False
    assert cfg.notifier.feishu.enabled is True
    assert cfg.notifier.feishu.receive_id_type == "user_id"
    assert cfg.notifier.feishu.receive_id == "fd6a7g21"


@pytest.mark.parametrize("receive_id_type", ["bad", "", "USER_ID"])
def test_load_config_rejects_invalid_feishu_receive_id_type(tmp_path, receive_id_type):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        VALID_TOML.replace('[notifier.feishu]\nenabled = false\nreceive_id_type = "user_id"\nreceive_id = ""',
                          f'[notifier.feishu]\nenabled = true\nreceive_id_type = "{receive_id_type}"\nreceive_id = "fd6a7g21"'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="receive_id_type"):
        load_config(cfg_file)


def test_load_config_requires_feishu_recipient_when_enabled(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        VALID_TOML.replace('[notifier.feishu]\nenabled = false', '[notifier.feishu]\nenabled = true'),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="receive_id"):
        load_config(cfg_file)


def test_load_config_requires_feishu_section_when_global_notifications_enabled(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(VALID_TOML.replace('[notifier]\nenabled = false', '[notifier]\nenabled = true')
                        .replace('[notifier.feishu]\nenabled = false', ''), encoding="utf-8")

    with pytest.raises(ValueError, match="receive_id"):
        load_config(cfg_file)
