import httpx
from loguru import logger


class Notifier:
    def __init__(self, webhook_url: str, enabled: bool):
        self._url = webhook_url
        self._enabled = enabled

    def _prefix(self, stage: str) -> str:
        return f"[zer0share · {stage}]"

    def _post_text(self, text: str) -> None:
        if not self._enabled:
            return
        payload = {
            "msgtype": "text",
            "text": {"content": text}
        }
        try:
            resp = httpx.post(self._url, json=payload, timeout=10)
            resp.raise_for_status()
        except httpx.RequestError as e:
            logger.error(f"webhook 推送失败: {e}")
        except httpx.HTTPStatusError as e:
            logger.error(f"webhook 返回错误: {e.response.status_code}")
        except Exception as e:
            logger.error(f"webhook 推送异常: {e}")

    def send(self, message: str) -> None:
        self._post_text(f"[zer0share] {message}")

    def notify_start(self, stage: str, details: dict) -> None:
        lines = [f"{self._prefix(stage)} 开始"]
        for k, v in details.items():
            lines.append(f"{k}: {v}")
        self._post_text("\n".join(lines))

    def notify_progress(self, stage: str, done: int, total: int) -> None:
        pct = int(done / total * 100)
        text = f"{self._prefix(stage)} 进度 {pct}% ({done}/{total})"
        self._post_text(text)

    def notify_stage_done(self, stage: str, summary: dict, elapsed: float) -> None:
        lines = [f"{self._prefix(stage)} 完成"]
        for k, v in summary.items():
            lines.append(f"{k}: {v}")
        lines.append(f"耗时: {elapsed}s")
        self._post_text("\n".join(lines))

    def notify_error(self, stage: str, error: str) -> None:
        text = f"{self._prefix(stage)} 错误: {error}"
        self._post_text(text)
