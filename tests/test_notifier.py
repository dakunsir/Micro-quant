import json
from unittest.mock import MagicMock, patch

import httpx

from zer0share.config import FeishuNotifierConfig, NotifierConfig, WeComNotifierConfig
from zer0share.notifier import CompositeNotifier, FeishuNotifier, NullNotifier, WeComNotifier, build_notifier


def test_wecom_disabled_does_not_call_http():
    n = WeComNotifier(webhook_url="https://example.com", enabled=False)
    with patch("httpx.post") as mock_post:
        n.send("test message")
        mock_post.assert_not_called()


def test_wecom_send_posts_text_payload():
    n = WeComNotifier(webhook_url="https://example.com/hook", enabled=True)
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    with patch("httpx.post", return_value=mock_response) as mock_post:
        n.send("同步完成：成功 5 天")

    payload = mock_post.call_args[1]["json"]
    assert payload == {
        "msgtype": "text",
        "text": {"content": "[zer0share] 同步完成：成功 5 天"},
    }


def test_wecom_request_error_does_not_raise():
    n = WeComNotifier(webhook_url="https://example.com/hook", enabled=True)
    with patch("httpx.post", side_effect=httpx.RequestError("network error", request=MagicMock())):
        n.send("告警消息")


def test_wecom_http_error_does_not_raise():
    n = WeComNotifier(webhook_url="https://example.com/hook", enabled=True)
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "400 Bad Request", request=MagicMock(), response=MagicMock(status_code=400)
    )
    with patch("httpx.post", return_value=mock_response):
        n.send("告警消息")


def test_feishu_builds_interactive_card_like_zer0factor():
    n = FeishuNotifier("https://open.feishu.cn/open-apis/bot/v2/hook/fake", app="zer0share")

    card = n._build_card(
        title="[zer0share] `ricequant_history` 完成",
        color="green",
        fields=[("行数", "22,475,520"), ("耗时", "257.4s")],
    )

    assert card["msg_type"] == "interactive"
    assert card["card"]["config"]["wide_screen_mode"] is True
    assert card["card"]["header"]["template"] == "green"
    assert card["card"]["header"]["title"]["content"] == "[zer0share] `ricequant_history` 完成"
    fields = card["card"]["elements"][0]["fields"]
    assert fields[0]["is_short"] is True
    assert fields[0]["text"]["tag"] == "lark_md"
    assert "**行数**\n22,475,520" == fields[0]["text"]["content"]


def test_feishu_notify_stage_done_sends_green_card():
    n = FeishuNotifier("https://open.feishu.cn/open-apis/bot/v2/hook/fake", app="zer0share")

    with patch.object(n, "_send") as mock_send:
        n.notify_stage_done("2026-05", {"行数": "22,475,520", "流量": "651 MiB"}, 257.4)

    card = mock_send.call_args[0][0]
    assert card["card"]["header"]["template"] == "green"
    assert "[zer0share] `2026-05` 完成" in card["card"]["header"]["title"]["content"]
    content = " ".join(f["text"]["content"] for f in card["card"]["elements"][0]["fields"])
    assert "22,475,520" in content
    assert "651 MiB" in content
    assert "257.4s" in content


def test_feishu_send_posts_json_to_webhook():
    n = FeishuNotifier("https://open.feishu.cn/open-apis/bot/v2/hook/fake", app="zer0share")
    card = n._build_card("标题", "green", [])
    with patch("urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__ = lambda s: s
        mock_open.return_value.__exit__ = MagicMock(return_value=False)
        n._send(card)

    req = mock_open.call_args[0][0]
    assert req.full_url == "https://open.feishu.cn/open-apis/bot/v2/hook/fake"
    body = json.loads(req.data)
    assert body["msg_type"] == "interactive"


def test_feishu_send_silences_network_errors():
    n = FeishuNotifier("https://open.feishu.cn/open-apis/bot/v2/hook/fake", app="zer0share")
    with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
        n._send(n._build_card("标题", "green", []))


def test_composite_notifier_fans_out():
    first = MagicMock()
    second = MagicMock()
    n = CompositeNotifier([first, second])

    n.notify_progress("ricequant_history", 3, 12)

    first.notify_progress.assert_called_once_with("ricequant_history", 3, 12)
    second.notify_progress.assert_called_once_with("ricequant_history", 3, 12)


def test_build_notifier_returns_null_when_disabled():
    cfg = NotifierConfig(
        enabled=False,
        wecom=WeComNotifierConfig(enabled=True, webhook_url="https://example.com/hook"),
        feishu=FeishuNotifierConfig(enabled=True, webhook_url="https://open.feishu.cn/hook"),
    )

    assert isinstance(build_notifier(cfg), NullNotifier)


def test_build_notifier_returns_composite_for_enabled_channels():
    cfg = NotifierConfig(
        enabled=True,
        wecom=WeComNotifierConfig(enabled=True, webhook_url="https://example.com/hook"),
        feishu=FeishuNotifierConfig(enabled=True, webhook_url="https://open.feishu.cn/hook"),
    )

    notifier = build_notifier(cfg)

    assert isinstance(notifier, CompositeNotifier)
    assert [type(n).__name__ for n in notifier.notifiers] == ["WeComNotifier", "FeishuNotifier"]
