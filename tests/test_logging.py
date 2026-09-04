from unittest.mock import patch

from microshare import logging as logging_module


def test_init_logger_defaults_to_info(tmp_path, monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    logging_module._logger_initialized = False

    with (
        patch("microshare.logging.logger.remove"),
        patch("microshare.logging.logger.add") as mock_add,
    ):
        logging_module.init_logger(tmp_path / "pipeline.log")

    levels = [call.kwargs["level"] for call in mock_add.call_args_list]
    assert levels == ["INFO", "INFO"]


def test_init_logger_uses_log_level_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    logging_module._logger_initialized = False

    with (
        patch("microshare.logging.logger.remove"),
        patch("microshare.logging.logger.add") as mock_add,
    ):
        logging_module.init_logger(tmp_path / "pipeline.log")

    levels = [call.kwargs["level"] for call in mock_add.call_args_list]
    assert levels == ["DEBUG", "DEBUG"]
