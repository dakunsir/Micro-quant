from dataclasses import dataclass
import ipaddress
from pathlib import Path
import re
import tomllib
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class RiceQuantStockMinuteConfig:
    request_sleep_seconds: float
    batch_size: int
    adjust_type: str
    skip_suspended: bool


@dataclass(frozen=True)
class RiceQuantETFMinuteConfig:
    enabled: bool
    request_sleep_seconds: float
    batch_size: int
    adjust_type: str
    skip_suspended: bool


@dataclass(frozen=True)
class FeishuNotifierConfig:
    enabled: bool
    receive_id: str
    receive_id_type: str


@dataclass(frozen=True)
class NotifierConfig:
    enabled: bool
    feishu: FeishuNotifierConfig


@dataclass(frozen=True)
class UniverseConfig:
    name: str
    version: str
    target_count: int
    min_listing_sessions: int
    exclude_st: bool
    main_board_prefixes: list[str]


@dataclass(frozen=True)
class RiceQuantConfig:
    enabled: bool
    username: str
    password: str
    license_key: str
    stock_minute: RiceQuantStockMinuteConfig
    etf_minute: RiceQuantETFMinuteConfig


@dataclass(frozen=True)
class QualityConfig:
    enabled: bool
    mode: str
    markets: list[str]
    notify_on: list[str]


@dataclass(frozen=True)
class ApiConfig:
    host: str
    port: int
    default_limit: int
    max_limit: int


@dataclass(frozen=True)
class SchedulerConfig:
    enabled: bool
    timezone: str
    run_time: str | None
    state_path: Path
    lock_path: Path


@dataclass(frozen=True)
class Config:
    tushare_token: str
    data_dir: Path
    db_path: Path
    log_path: Path
    schedule: dict[str, str]  # table_name → "HH:MM"
    notifier: NotifierConfig
    universe: UniverseConfig
    ricequant: RiceQuantConfig
    quality: QualityConfig
    api: ApiConfig
    scheduler: SchedulerConfig


def _parse_ricequant(raw: dict) -> RiceQuantConfig:
    raw_rq = raw.get("ricequant", {})
    raw_stock_minute = raw_rq.get("stock_minute", {})
    adjust_type = raw_stock_minute.get("adjust_type", "none")
    if adjust_type != "none":
        raise ValueError("ricequant.stock_minute.adjust_type currently only supports 'none'")

    raw_etf_minute = raw_rq.get("etf_minute", {})
    etf_adjust_type = raw_etf_minute.get("adjust_type", "none")
    if etf_adjust_type != "none":
        raise ValueError("ricequant.etf_minute.adjust_type currently only supports 'none'")

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
            batch_size=int(raw_stock_minute.get("batch_size", 1000)),
            adjust_type=adjust_type,
            skip_suspended=bool(raw_stock_minute.get("skip_suspended", True)),
        ),
        etf_minute=RiceQuantETFMinuteConfig(
            enabled=bool(raw_etf_minute.get("enabled", False)),
            request_sleep_seconds=float(raw_etf_minute.get("request_sleep_seconds", 0.2)),
            batch_size=int(raw_etf_minute.get("batch_size", 500)),
            adjust_type=etf_adjust_type,
            skip_suspended=bool(raw_etf_minute.get("skip_suspended", True)),
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


def _parse_api(raw: dict) -> ApiConfig:
    raw_api = raw.get("api", {})
    if not isinstance(raw_api, dict):
        raise ValueError("[api] 必须是配置表")

    host = str(raw_api.get("host", "127.0.0.1")).strip()
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        if host != "localhost":
            raise ValueError("api.host 必须是回环地址 127.0.0.1、::1 或 localhost") from exc
        address = None
    if address is not None and not address.is_loopback:
        raise ValueError("api.host 必须是回环地址 127.0.0.1、::1 或 localhost")

    port = int(raw_api.get("port", 8787))
    default_limit = int(raw_api.get("default_limit", 1000))
    max_limit = int(raw_api.get("max_limit", 5000))
    if not 1 <= port <= 65535:
        raise ValueError("api.port 必须在 1 到 65535 之间")
    if default_limit < 1 or max_limit < 1 or default_limit > max_limit:
        raise ValueError("api.default_limit 和 api.max_limit 必须为正数且 default_limit <= max_limit")
    if max_limit > 5000:
        raise ValueError("api.max_limit 不能超过 5000")
    return ApiConfig(
        host=host,
        port=port,
        default_limit=default_limit,
        max_limit=max_limit,
    )


def _parse_scheduler(raw: dict) -> tuple[SchedulerConfig, dict[str, str]]:
    raw_scheduler = raw.get("scheduler", {})
    if not isinstance(raw_scheduler, dict):
        raise ValueError("[scheduler] 必须是配置表")

    fixed_keys = {"enabled", "timezone", "run_time", "state_path", "lock_path"}
    legacy_raw = {key: value for key, value in raw_scheduler.items() if key not in fixed_keys}
    legacy_schedule = _parse_schedule(legacy_raw)

    run_time_raw = raw_scheduler.get("run_time")
    run_time = None if run_time_raw is None and legacy_schedule else str(run_time_raw or "18:30")
    enabled_default = bool(legacy_schedule) if run_time is None else False
    enabled = bool(raw_scheduler.get("enabled", enabled_default))
    if run_time is not None:
        _parse_schedule({"run_time": run_time})

    timezone = str(raw_scheduler.get("timezone", "Asia/Shanghai")).strip()
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"scheduler.timezone 无效: {timezone}") from exc

    return (
        SchedulerConfig(
            enabled=enabled,
            timezone=timezone,
            run_time=run_time,
            state_path=Path(raw_scheduler.get("state_path", "db/scheduler/latest_run.json")),
            lock_path=Path(raw_scheduler.get("lock_path", "db/scheduler/run.lock")),
        ),
        legacy_schedule,
    )


def _parse_notifier(raw: dict) -> NotifierConfig:
    raw_notifier = raw.get("notifier", {})
    unsupported_keys = sorted(set(raw_notifier) - {"enabled", "feishu"})
    if unsupported_keys:
        raise ValueError(
            "通知配置包含已移除或不支持的字段: "
            f"{', '.join(unsupported_keys)}；请迁移到 [notifier.feishu]"
        )

    enabled = bool(raw_notifier.get("enabled", False))
    raw_feishu = raw_notifier.get("feishu", {})
    if not isinstance(raw_feishu, dict):
        raise ValueError("[notifier.feishu] 必须是配置表")

    receive_id = str(raw_feishu.get("receive_id", "")).strip()
    receive_id_type = str(raw_feishu.get("receive_id_type", "")).strip()
    valid_types = {"open_id", "union_id", "user_id", "email", "chat_id"}
    if receive_id_type and receive_id_type not in valid_types:
        raise ValueError(
            "notifier.feishu.receive_id_type 必须是 "
            "open_id、union_id、user_id、email 或 chat_id"
        )

    feishu_enabled = bool(raw_feishu.get("enabled", enabled))
    if feishu_enabled and (not receive_id or not receive_id_type):
        raise ValueError(
            "启用飞书通知时必须配置 notifier.feishu.receive_id 和 receive_id_type"
        )
    return NotifierConfig(
        enabled=enabled,
        feishu=FeishuNotifierConfig(
            enabled=feishu_enabled,
            receive_id=receive_id,
            receive_id_type=receive_id_type,
        ),
    )


def _parse_universe(raw: dict) -> UniverseConfig:
    raw_universe = raw.get("universe", {})
    if not isinstance(raw_universe, dict):
        raise ValueError("[universe] 必须是配置表")

    name = str(
        raw_universe.get(
            "name", "hushen_mainboard_previous_day_bottom1000"
        )
    ).strip()
    version = str(raw_universe.get("version", "current")).strip()
    target_count = int(raw_universe.get("target_count", 1000))
    min_listing_sessions = int(raw_universe.get("min_listing_sessions", 120))
    exclude_st = bool(raw_universe.get("exclude_st", True))
    prefixes = raw_universe.get(
        "main_board_prefixes",
        ["600", "601", "603", "605", "000", "001", "002", "003"],
    )
    if not name:
        raise ValueError("universe.name 不能为空")
    if not version:
        raise ValueError("universe.version 不能为空")
    if target_count <= 0:
        raise ValueError("universe.target_count 必须大于 0")
    if min_listing_sessions < 0:
        raise ValueError("universe.min_listing_sessions 不能小于 0")
    if not isinstance(prefixes, list) or not prefixes:
        raise ValueError("universe.main_board_prefixes 必须是非空列表")
    normalized_prefixes = [str(prefix).strip() for prefix in prefixes]
    if any(not prefix.isdigit() or len(prefix) != 3 for prefix in normalized_prefixes):
        raise ValueError("universe.main_board_prefixes 必须是三位数字前缀")
    return UniverseConfig(
        name=name,
        version=version,
        target_count=target_count,
        min_listing_sessions=min_listing_sessions,
        exclude_st=exclude_st,
        main_board_prefixes=normalized_prefixes,
    )


def _parse_quality(raw_quality: dict | None) -> QualityConfig:
    raw_quality = raw_quality or {}
    return QualityConfig(
        enabled=bool(raw_quality.get("enabled", False)),
        mode=str(raw_quality.get("mode", "daily")),
        markets=list(raw_quality.get("markets", ["stock", "index", "etf", "futures", "options"])),
        notify_on=list(raw_quality.get("notify_on", ["warn", "fail"])),
    )


def load_config(path: Path = Path("config/settings.toml")) -> Config:
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    try:
        with open(path, "rb") as f:
            raw = tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"配置文件格式错误: {e}") from e
    try:
        notifier = _parse_notifier(raw)
        universe = _parse_universe(raw)
        scheduler, schedule = _parse_scheduler(raw)
        return Config(
            tushare_token=raw["tushare"]["token"],
            data_dir=Path(raw["paths"]["data_dir"]),
            db_path=Path(raw["paths"]["db_path"]),
            log_path=Path(raw["paths"]["log_path"]),
            schedule=schedule,
            notifier=notifier,
            universe=universe,
            ricequant=_parse_ricequant(raw),
            quality=_parse_quality(raw.get("quality")),
            api=_parse_api(raw),
            scheduler=scheduler,
        )
    except KeyError as e:
        raise KeyError(f"配置文件缺少必要字段: {e}") from e
