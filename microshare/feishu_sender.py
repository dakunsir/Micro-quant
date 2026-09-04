"""Send text messages through the Feishu application API."""

from __future__ import annotations

import json
import os
from uuid import uuid4


RECEIVE_ID_TYPES = ("open_id", "union_id", "user_id", "email", "chat_id")

# Deployment can override these with FEISHU_APP_ID/FEISHU_APP_SECRET.
DEFAULT_FEISHU_APP_ID = "cli_aa192e0b41f8dbfc"
DEFAULT_FEISHU_APP_SECRET = "Kd0CXzBvdmM9htEgHNWWQc0EV0WICsBR"


def send_text_message(
    receive_id: str,
    receive_id_type: str,
    text: str,
    *,
    uuid: str | None = None,
) -> dict:
    """Send one text message and return a serializable result mapping."""
    if receive_id_type not in RECEIVE_ID_TYPES:
        return {
            "success": False,
            "error": f"unsupported receive_id_type: {receive_id_type}",
        }

    app_id = os.environ.get("FEISHU_APP_ID", DEFAULT_FEISHU_APP_ID).strip()
    app_secret = os.environ.get("FEISHU_APP_SECRET", DEFAULT_FEISHU_APP_SECRET).strip()
    if not app_id or not app_secret:
        return {
            "success": False,
            "error": "FEISHU_APP_ID and FEISHU_APP_SECRET are required",
        }

    try:
        import lark_oapi as lark
        from lark_oapi.api.im.v1 import (
            CreateMessageRequest,
            CreateMessageRequestBody,
        )

        client = (
            lark.Client.builder()
            .app_id(app_id)
            .app_secret(app_secret)
            .log_level(lark.LogLevel.ERROR)
            .build()
        )
        request = (
            CreateMessageRequest.builder()
            .receive_id_type(receive_id_type)
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(receive_id)
                .msg_type("text")
                .content(json.dumps({"text": text}, ensure_ascii=False))
                .uuid(uuid or str(uuid4()))
                .build()
            )
            .build()
        )
        response = client.im.v1.message.create(request)
    except Exception as exc:
        return {"success": False, "error": str(exc)}

    if not response.success():
        return {
            "success": False,
            "code": response.code,
            "msg": response.msg,
            "log_id": response.get_log_id(),
        }

    data = response.data
    return {
        "success": True,
        "message_id": getattr(data, "message_id", None),
        "chat_id": getattr(data, "chat_id", None),
        "receive_id_type": receive_id_type,
    }
