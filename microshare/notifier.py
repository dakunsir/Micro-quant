from __future__ import annotations

from typing import Protocol
from uuid import uuid4

from loguru import logger

from microshare.config import NotifierConfig
from microshare.feishu_sender import send_text_message


class NotifierProtocol(Protocol):
    def send(self, message: str) -> None: ...

    def notify_start(self, stage: str, details: dict | None = None) -> None: ...

    def notify_progress(self, stage: str, done: int, total: int) -> None: ...

    def notify_stage_done(self, stage: str, summary: dict, elapsed: float) -> None: ...

    def notify_error(self, stage: str, error) -> None: ...


class NullNotifier:
    def send(self, message: str) -> None:
        pass

    def notify_start(self, stage: str, details: dict | None = None) -> None:
        pass

    def notify_progress(self, stage: str, done: int, total: int) -> None:
        pass

    def notify_stage_done(self, stage: str, summary: dict, elapsed: float) -> None:
        pass

    def notify_error(self, stage: str, error) -> None:
        pass


class FeishuNotifier:
    def __init__(
        self,
        receive_id: str,
        receive_id_type: str,
        *,
        app: str = "Microshare",
        enabled: bool = True,
    ) -> None:
        self._receive_id = receive_id
        self._receive_id_type = receive_id_type
        self._app = app
        self._enabled = enabled

    def _prefix(self, stage: str) -> str:
        return f"[{self._app} · {stage}]"

    def _post_text(self, text: str) -> None:
        if not self._enabled or not self._receive_id or not self._receive_id_type:
            return
        try:
            result = send_text_message(
                self._receive_id,
                self._receive_id_type,
                text,
                uuid=str(uuid4()),
            )
        except Exception as exc:
            logger.error(f"飞书推送异常: {exc}")
            return
        if not result.get("success"):
            logger.error(
                "飞书推送失败: code={} msg={} log_id={}",
                result.get("code"),
                result.get("msg"),
                result.get("log_id"),
            )

    def send(self, message: str) -> None:
        self._post_text(f"[{self._app}] {message}")

    def notify_start(self, stage: str, details: dict | None = None) -> None:
        lines = [f"{self._prefix(stage)} 开始"]
        lines.extend(f"{key}: {value}" for key, value in (details or {}).items())
        self._post_text("\n".join(lines))

    def notify_progress(self, stage: str, done: int, total: int) -> None:
        if total == 0:
            return
        pct = round(done / total * 100)
        self._post_text(f"{self._prefix(stage)} 进度 {pct}% ({done}/{total})")

    def notify_stage_done(self, stage: str, summary: dict, elapsed: float) -> None:
        lines = [f"{self._prefix(stage)} 完成"]
        lines.extend(f"{key}: {value}" for key, value in summary.items())
        lines.append(f"耗时: {elapsed:.1f}s")
        self._post_text("\n".join(lines))

    def notify_error(self, stage: str, error) -> None:
        detail = (
            f"{type(error).__name__}: {error}"
            if isinstance(error, BaseException)
            else str(error)
        )
        self._post_text(f"{self._prefix(stage)} 错误\n{detail}")


def build_notifier(cfg: NotifierConfig) -> NotifierProtocol:
    if not cfg.enabled or not cfg.feishu.enabled:
        return NullNotifier()
    return FeishuNotifier(
        cfg.feishu.receive_id,
        cfg.feishu.receive_id_type,
        enabled=True,
    )


Notifier = FeishuNotifier
