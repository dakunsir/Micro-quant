from uuid import UUID
from unittest.mock import patch

from microshare.config import FeishuNotifierConfig, NotifierConfig
from microshare.notifier import FeishuNotifier, NullNotifier, build_notifier


def _notifier(*, enabled: bool = True) -> FeishuNotifier:
    return FeishuNotifier(
        "fd6a7g21",
        "user_id",
        enabled=enabled,
    )


def test_disabled_does_not_call_sender():
    with patch("microshare.notifier.send_text_message") as send_message:
        _notifier(enabled=False).send("test message")
    send_message.assert_not_called()


def test_send_passes_prefixed_text_recipient_and_uuid():
    with patch(
        "microshare.notifier.send_text_message",
        return_value={"success": True, "message_id": "om_123"},
    ) as send_message:
        _notifier().send("同步完成：成功 5 天")

    args, kwargs = send_message.call_args
    assert args[:2] == ("fd6a7g21", "user_id")
    assert args[2] == "[Microshare] 同步完成：成功 5 天"
    UUID(kwargs["uuid"])


def test_notify_start_includes_details():
    with patch("microshare.notifier.send_text_message", return_value={"success": True}) as send_message:
        _notifier().notify_start("daily", {"日期": "2026-09-04", "行数": 3})

    text = send_message.call_args.args[2]
    assert text == "[Microshare · daily] 开始\n日期: 2026-09-04\n行数: 3"


def test_notify_progress_includes_percent_and_counts():
    with patch("microshare.notifier.send_text_message", return_value={"success": True}) as send_message:
        _notifier().notify_progress("daily", 3, 4)

    assert send_message.call_args.args[2] == "[Microshare · daily] 进度 75% (3/4)"


def test_notify_progress_skips_empty_total():
    with patch("microshare.notifier.send_text_message") as send_message:
        _notifier().notify_progress("daily", 0, 0)
    send_message.assert_not_called()


def test_notify_stage_done_includes_summary_and_elapsed():
    with patch("microshare.notifier.send_text_message", return_value={"success": True}) as send_message:
        _notifier().notify_stage_done("daily", {"成功": 5, "失败": 1}, 2.34)

    text = send_message.call_args.args[2]
    assert text == "[Microshare · daily] 完成\n成功: 5\n失败: 1\n耗时: 2.3s"


def test_notify_error_includes_exception_type_and_message():
    with patch("microshare.notifier.send_text_message", return_value={"success": True}) as send_message:
        _notifier().notify_error("daily", RuntimeError("timeout"))

    assert send_message.call_args.args[2] == "[Microshare · daily] 错误\nRuntimeError: timeout"


def test_sender_exception_does_not_raise_and_is_logged():
    with (
        patch("microshare.notifier.send_text_message", side_effect=OSError("network down")),
        patch("microshare.notifier.logger.error") as log_error,
    ):
        _notifier().send("告警消息")

    log_error.assert_called_once()
    assert "network down" in str(log_error.call_args)


def test_api_error_does_not_raise_and_logs_code_message_and_log_id():
    result = {"success": False, "code": 999, "msg": "permission denied", "log_id": "log_123"}
    with (
        patch("microshare.notifier.send_text_message", return_value=result),
        patch("microshare.notifier.logger.error") as log_error,
    ):
        _notifier().send("告警消息")

    log_error.assert_called_once()
    assert log_error.call_args.args == (
        "飞书推送失败: code={} msg={} log_id={}",
        999,
        "permission denied",
        "log_123",
    )


def test_build_notifier_returns_null_when_disabled():
    cfg = NotifierConfig(
        enabled=False,
        feishu=FeishuNotifierConfig(
            enabled=True,
            receive_id="fd6a7g21",
            receive_id_type="user_id",
        ),
    )

    assert isinstance(build_notifier(cfg), NullNotifier)


def test_build_notifier_returns_feishu_when_enabled():
    cfg = NotifierConfig(
        enabled=True,
        feishu=FeishuNotifierConfig(
            enabled=True,
            receive_id="fd6a7g21",
            receive_id_type="user_id",
        ),
    )

    notifier = build_notifier(cfg)

    assert isinstance(notifier, FeishuNotifier)
