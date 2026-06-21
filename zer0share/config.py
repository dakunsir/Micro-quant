from dataclasses import dataclass
from pathlib import Path
import re
import tomllib


@dataclass(frozen=True)
class RiceQuantStockMinuteConfig:
    request_sleep_seconds: float
    adjust_type: str
    skip_suspended: bool


@dataclass(frozen=True)
class RiceQuantConfig:
    enabled: bool
    username: str
    password: str
    license_key: str
    stock_minute: RiceQuantStockMinuteConfig


@dataclass(frozen=True)
class Config:
    tushare_token: str
    data_dir: Path
    db_path: Path
    log_path: Path
    schedule: dict[str, str]  # table_name → "HH:MM"
    wecom_webhook_url: str
    notifier_enabled: bool
    ricequant: RiceQuantConfig


def _parse_ricequant(raw: dict) -> RiceQuantConfig:
    raw_rq = raw.get("ricequant", {})
    raw_stock_minute = raw_rq.get("stock_minute", {})
    adjust_type = raw_stock_minute.get("adjust_type", "none")
    if adjust_type != "none":
        raise ValueError("ricequant.stock_minute.adjust_type currently only supports 'none'")
    enabled = bool(raw_rq.get("enabled", False))
    username = str(raw_rq.get("username", ""))
    password = str(raw_rq.get("password", ""))
    license_key = str(raw_rq.get("license_key", ""))
    has_user_password = bool(username or password)
    if enabled and license_key and has_user_password:
        raise ValueError("ricequant credentials must use either license_key or username/password, not both")
    if enabled and license_key == "" and not (username and password):
        raise ValueError("ricequant credentials require license_key or both username and password")
    return RiceQuantConfig(
        enabled=enabled,
        username=username,
        password=password,
        license_key=license_key,
        stock_minute=RiceQuantStockMinuteConfig(
            request_sleep_seconds=float(raw_stock_minute.get("request_sleep_seconds", 0.2)),
            adjust_type=adjust_type,
            skip_suspended=bool(raw_stock_minute.get("skip_suspended", True)),
        ),
    )


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


def load_config(path: Path = Path("config/settings.toml")) -> Config:
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"配置文件格式错误: {e}") from e
    try:
        return Config(
            tushare_token=raw["tushare"]["token"],
            data_dir=Path(raw["paths"]["data_dir"]),
            db_path=Path(raw["paths"]["db_path"]),
            log_path=Path(raw["paths"]["log_path"]),
            schedule=_parse_schedule(raw["scheduler"]),
            wecom_webhook_url=raw["notifier"]["wecom_webhook_url"],
            notifier_enabled=raw["notifier"]["enabled"],
            ricequant=_parse_ricequant(raw),
        )
    except KeyError as e:
        raise KeyError(f"配置文件缺少必要字段: {e}") from e
