from dataclasses import dataclass
from pathlib import Path
import re
import tomllib


@dataclass(frozen=True)
class QualityConfig:
    enabled: bool
    mode: str
    markets: list[str]
    notify_on: list[str]


@dataclass(frozen=True)
class Config:
    tushare_token: str
    data_dir: Path
    db_path: Path
    log_path: Path
    schedule: dict[str, str]  # table_name → "HH:MM"
    wecom_webhook_url: str
    notifier_enabled: bool
    quality: QualityConfig


def _parse_schedule(raw_scheduler: dict) -> dict[str, str]:
    schedule = {}
    pattern = re.compile(r"^\d{1,2}:\d{2}$")
    for table, time_str in raw_scheduler.items():
        if not isinstance(time_str, str) or not pattern.match(time_str):
            raise ValueError(f"调度时间格式错误 ({table}): 期望 'HH:MM', 得到 {time_str!r}")
        hour, minute = int(time_str.split(":")[0]), int(time_str.split(":")[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(f"调度时间格式错误 ({table}): 期望 'HH:MM', 得到 {time_str!r}")
        schedule[table] = time_str
    return schedule


def _parse_quality(raw_quality: dict | None) -> QualityConfig:
    raw_quality = raw_quality or {}
    return QualityConfig(
        enabled=bool(raw_quality.get("enabled", False)),
        mode=str(raw_quality.get("mode", "daily")),
        markets=list(raw_quality.get("markets", ["stock", "index", "etf", "futures", "options"])),
        notify_on=list(raw_quality.get("notify_on", ["warn", "fail"])),
    )


def _parse_wecom_notifier(raw_notifier: dict) -> tuple[str, bool]:
    if "wecom_webhook_url" in raw_notifier:
        return raw_notifier["wecom_webhook_url"], bool(raw_notifier["enabled"])

    raw_wecom = raw_notifier.get("wecom", {})
    webhook_url = raw_wecom.get("webhook_url", "")
    enabled = bool(raw_notifier.get("enabled", False)) and bool(raw_wecom.get("enabled", False))
    return webhook_url, enabled


def load_config(path: Path = Path("config/settings.toml")) -> Config:
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"配置文件格式错误: {e}") from e
    try:
        wecom_webhook_url, notifier_enabled = _parse_wecom_notifier(raw["notifier"])
        return Config(
            tushare_token=raw["tushare"]["token"],
            data_dir=Path(raw["paths"]["data_dir"]),
            db_path=Path(raw["paths"]["db_path"]),
            log_path=Path(raw["paths"]["log_path"]),
            schedule=_parse_schedule(raw["scheduler"]),
            wecom_webhook_url=wecom_webhook_url,
            notifier_enabled=notifier_enabled,
            quality=_parse_quality(raw.get("quality")),
        )
    except KeyError as e:
        raise KeyError(f"配置文件缺少必要字段: {e}") from e
