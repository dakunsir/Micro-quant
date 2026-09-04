import json
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from microshare.feishu_sender import send_text_message


def _fake_sdk(response):
    captured = {}

    class BodyBuilder:
        def receive_id(self, value):
            captured["receive_id"] = value
            return self

        def msg_type(self, value):
            captured["msg_type"] = value
            return self

        def content(self, value):
            captured["content"] = value
            return self

        def uuid(self, value):
            captured["uuid"] = value
            return self

        def build(self):
            return SimpleNamespace(**captured)

    class RequestBuilder:
        def receive_id_type(self, value):
            captured["receive_id_type"] = value
            return self

        def request_body(self, value):
            captured["request_body"] = value
            return self

        def build(self):
            return SimpleNamespace(**captured)

    class ClientBuilder:
        def app_id(self, value):
            captured["app_id"] = value
            return self

        def app_secret(self, value):
            captured["app_secret"] = value
            return self

        def log_level(self, value):
            return self

        def build(self):
            return SimpleNamespace(
                im=SimpleNamespace(v1=SimpleNamespace(message=SimpleNamespace(create=lambda request: response)))
            )

    v1 = ModuleType("lark_oapi.api.im.v1")
    v1.CreateMessageRequest = SimpleNamespace(builder=RequestBuilder)
    v1.CreateMessageRequestBody = SimpleNamespace(builder=BodyBuilder)
    im = ModuleType("lark_oapi.api.im")
    im.v1 = v1
    api = ModuleType("lark_oapi.api")
    api.im = im
    lark = ModuleType("lark_oapi")
    lark.Client = SimpleNamespace(builder=ClientBuilder)
    lark.LogLevel = SimpleNamespace(ERROR="ERROR")
    return {"lark_oapi": lark, "lark_oapi.api": api, "lark_oapi.api.im": im, "lark_oapi.api.im.v1": v1}, captured


def test_sender_uses_embedded_application_credentials(monkeypatch):
    monkeypatch.delenv("FEISHU_APP_ID", raising=False)
    monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
    response = SimpleNamespace(
        success=lambda: True,
        data=SimpleNamespace(message_id="om_embedded", chat_id="oc_123"),
    )
    modules, captured = _fake_sdk(response)
    with patch.dict(sys.modules, modules):
        result = send_text_message("fd6a7g21", "user_id", "hello", uuid="uuid-embedded")

    assert result["success"] is True
    assert captured["app_id"].startswith("cli_")
    assert captured["app_secret"]


def test_sender_environment_credentials_override_embedded_values(monkeypatch):
    monkeypatch.setenv("FEISHU_APP_ID", "app-from-env")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret-from-env")
    response = SimpleNamespace(
        success=lambda: True,
        data=SimpleNamespace(message_id="om_env", chat_id="oc_123"),
    )
    modules, captured = _fake_sdk(response)
    with patch.dict(sys.modules, modules):
        result = send_text_message("fd6a7g21", "user_id", "hello")

    assert result["success"] is True
    assert captured["app_id"] == "app-from-env"
    assert captured["app_secret"] == "secret-from-env"


def test_sender_rejects_invalid_receive_type(monkeypatch):
    monkeypatch.setenv("FEISHU_APP_ID", "app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret")

    result = send_text_message("fd6a7g21", "invalid", "hello")

    assert result["success"] is False
    assert "unsupported receive_id_type" in result["error"]


def test_sender_returns_message_id_on_sdk_success(monkeypatch):
    monkeypatch.setenv("FEISHU_APP_ID", "app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret")
    response = SimpleNamespace(
        success=lambda: True,
        data=SimpleNamespace(message_id="om_123", chat_id="oc_123"),
    )
    modules, captured = _fake_sdk(response)
    with patch.dict(sys.modules, modules):
        result = send_text_message("fd6a7g21", "user_id", "hello", uuid="uuid-123")

    assert result == {
        "success": True,
        "message_id": "om_123",
        "chat_id": "oc_123",
        "receive_id_type": "user_id",
    }
    assert captured["app_id"] == "app"
    assert captured["app_secret"] == "secret"
    assert captured["receive_id"] == "fd6a7g21"
    assert captured["receive_id_type"] == "user_id"
    assert captured["msg_type"] == "text"
    assert captured["uuid"] == "uuid-123"
    assert json.loads(captured["content"]) == {"text": "hello"}


def test_sender_returns_api_error_details(monkeypatch):
    monkeypatch.setenv("FEISHU_APP_ID", "app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret")
    response = SimpleNamespace(
        success=lambda: False,
        code=999,
        msg="permission denied",
        get_log_id=lambda: "log_123",
    )
    modules, _ = _fake_sdk(response)
    with patch.dict(sys.modules, modules):
        result = send_text_message("fd6a7g21", "user_id", "hello")

    assert result == {
        "success": False,
        "code": 999,
        "msg": "permission denied",
        "log_id": "log_123",
    }
