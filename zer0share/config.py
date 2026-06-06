from dataclasses import dataclass
from pathlib import Path
import re
import tomllib


@dataclass(frozen=True)
class Config:
    tushare_token: str
    data_dir: Path
    db_path: Path
    log_path: Path
    schedule: dict[str, str]  # table_name → "HH:MM"
    wecom_webhook_url: str
    notifier_enabled: bool


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
        )
    except KeyError as e:
        raise KeyError(f"配置文件缺少必要字段: {e}") from e
