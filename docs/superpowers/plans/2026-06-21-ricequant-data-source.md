# RiceQuant Data Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add RiceQuant as a private, isolated data source with A-share 1-minute sync and an independent local `rq_api()` query entrypoint.

**Architecture:** Keep Tushare behavior behind the existing `pro_api()` path and add RiceQuant behind separate source, sync, storage path, and query modules. RiceQuant stock minute data is stored under `data/ricequant/stock_minute/date=YYYYMMDD/data.parquet`, uses `ricequant_stock_minute` as the sync table name, and is queried through `rq_api().get_price(order_book_ids, frequency="1m")`.

**Tech Stack:** Python 3.11, pandas, pyarrow Parquet, DuckDB, click, pytest, optional `rqdatac`.

---

## File Structure

- Create `zer0share/sources/__init__.py`: `DataSources` container and source exports.
- Create `zer0share/sources/tushare.py`: moved Tushare fetcher implementation.
- Modify `zer0share/fetcher.py`: compatibility shim that re-exports Tushare names.
- Create `zer0share/sources/ricequant.py`: optional `rqdatac` adapter and RiceQuant code conversion helpers.
- Modify `zer0share/config.py`: add `RiceQuantConfig` and optional `[ricequant]` parsing.
- Modify `config/settings.example.toml`: add disabled RiceQuant example and `ricequant_stock_minute` schedule.
- Modify `pyproject.toml`: add `rqdatac` dependency only if the private environment should install it through `uv`; otherwise keep optional import only. Prefer adding it on this private branch.
- Modify `zer0share/pipeline.py`, `zer0share/cli.py`, `zer0share/scheduler.py`: construct and pass `DataSources`.
- Create `zer0share/sync/ricequant.py`: `RiceQuantStockMinuteSyncJob`.
- Create `zer0share/query/ricequant.py`: local RiceQuant Parquet query helpers.
- Create `zer0share/rq_api.py`: public local RiceQuant API.
- Modify `zer0share/__init__.py`: export `rq_api` and `RQLocal`.
- Modify docs: `README.md`, `docs/SYNC_GUIDE.md`, `skills/zer0share-data/references/api.md`.
- Add tests: `tests/test_ricequant_fetcher.py`, `tests/test_ricequant_sync.py`, `tests/test_rq_api.py`; extend `tests/test_config.py`, `tests/test_pipeline.py`, `tests/test_cli.py`, `tests/test_scheduler.py`, `tests/test_api.py`.

## Task 1: Config And Dependency

**Files:**
- Modify: `zer0share/config.py`
- Modify: `config/settings.example.toml`
- Modify: `pyproject.toml`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing config tests**

Add these tests to `tests/test_config.py`:

```python
def test_load_config_defaults_ricequant_disabled(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(VALID_TOML, encoding="utf-8")

    cfg = load_config(cfg_file)

    assert cfg.ricequant.enabled is False
    assert cfg.ricequant.username == ""
    assert cfg.ricequant.password == ""
    assert cfg.ricequant.license_key == ""
    assert cfg.ricequant.request_sleep_seconds == 0.2
    assert cfg.ricequant.adjust_type == "none"
    assert cfg.ricequant.skip_suspended is True


def test_load_config_parses_ricequant_section(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        VALID_TOML
        + """

[ricequant]
enabled = true
username = "rq_user"
password = "rq_password"
license_key = ""
request_sleep_seconds = 0.5
adjust_type = "none"
skip_suspended = false
""",
        encoding="utf-8",
    )

    cfg = load_config(cfg_file)

    assert cfg.ricequant.enabled is True
    assert cfg.ricequant.username == "rq_user"
    assert cfg.ricequant.password == "rq_password"
    assert cfg.ricequant.license_key == ""
    assert cfg.ricequant.request_sleep_seconds == 0.5
    assert cfg.ricequant.adjust_type == "none"
    assert cfg.ricequant.skip_suspended is False


def test_load_config_parses_ricequant_license_key(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        VALID_TOML
        + """

[ricequant]
enabled = true
license_key = "rq_license_key"
""",
        encoding="utf-8",
    )

    cfg = load_config(cfg_file)

    assert cfg.ricequant.enabled is True
    assert cfg.ricequant.username == ""
    assert cfg.ricequant.password == ""
    assert cfg.ricequant.license_key == "rq_license_key"


def test_load_config_rejects_ambiguous_ricequant_credentials(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        VALID_TOML
        + """

[ricequant]
enabled = true
username = "rq_user"
password = "rq_password"
license_key = "rq_license_key"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="ricequant credentials"):
        load_config(cfg_file)


def test_load_config_rejects_enabled_ricequant_without_credentials(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        VALID_TOML
        + """

[ricequant]
enabled = true
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="ricequant credentials"):
        load_config(cfg_file)


def test_load_config_rejects_unsupported_ricequant_adjust_type(tmp_path):
    cfg_file = tmp_path / "settings.toml"
    cfg_file.write_text(
        VALID_TOML
        + """

[ricequant]
enabled = true
username = "rq_user"
password = "rq_password"
adjust_type = "pre"
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="ricequant.adjust_type"):
        load_config(cfg_file)
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_config.py -q
```

Expected: the new tests fail because `Config` has no `ricequant` attribute.

- [ ] **Step 3: Implement config parsing**

Modify `zer0share/config.py`:

```python
@dataclass(frozen=True)
class RiceQuantConfig:
    enabled: bool
    username: str
    password: str
    license_key: str
    request_sleep_seconds: float
    adjust_type: str
    skip_suspended: bool


@dataclass(frozen=True)
class Config:
    tushare_token: str
    data_dir: Path
    db_path: Path
    log_path: Path
    schedule: dict[str, str]
    wecom_webhook_url: str
    notifier_enabled: bool
    ricequant: RiceQuantConfig
```

Add helper:

```python
def _parse_ricequant(raw: dict) -> RiceQuantConfig:
    raw_rq = raw.get("ricequant", {})
    adjust_type = raw_rq.get("adjust_type", "none")
    if adjust_type != "none":
        raise ValueError("ricequant.adjust_type currently only supports 'none'")
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
        request_sleep_seconds=float(raw_rq.get("request_sleep_seconds", 0.2)),
        adjust_type=adjust_type,
        skip_suspended=bool(raw_rq.get("skip_suspended", True)),
    )
```

Pass it from `load_config`:

```python
ricequant=_parse_ricequant(raw),
```

- [ ] **Step 4: Update example config and dependency**

Add to `config/settings.example.toml`:

```toml
[ricequant]
enabled = false
username = ""
password = ""
license_key = ""
request_sleep_seconds = 0.2
adjust_type = "none"
skip_suspended = true
```

Add this scheduler entry:

```toml
ricequant_stock_minute = "16:30"
```

Add to `pyproject.toml` dependencies:

```toml
"rqdatac>=3.0",
```

- [ ] **Step 5: Run tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_config.py -q
```

Expected: all config tests pass.

- [ ] **Step 6: Commit**

```bash
git add zer0share/config.py config/settings.example.toml pyproject.toml tests/test_config.py
git commit -m "feat: add ricequant config"
```

## Task 2: Source Adapters

**Files:**
- Create: `zer0share/sources/__init__.py`
- Create: `zer0share/sources/tushare.py`
- Create: `zer0share/sources/ricequant.py`
- Modify: `zer0share/fetcher.py`
- Test: `tests/test_fetcher.py`
- Test: `tests/test_ricequant_fetcher.py`

- [ ] **Step 1: Write failing RiceQuant fetcher tests**

Create `tests/test_ricequant_fetcher.py`:

```python
import sys
import types

import pandas as pd
import pytest

from zer0share.sources.ricequant import (
    RiceQuantFetcher,
    ricequant_to_ts_code,
    ts_code_to_ricequant,
)


def test_ts_code_to_ricequant_converts_a_share_suffixes():
    assert ts_code_to_ricequant("000001.SZ") == "000001.XSHE"
    assert ts_code_to_ricequant("600000.SH") == "600000.XSHG"


def test_ricequant_to_ts_code_converts_a_share_suffixes():
    assert ricequant_to_ts_code("000001.XSHE") == "000001.SZ"
    assert ricequant_to_ts_code("600000.XSHG") == "600000.SH"


def test_ricequant_code_conversion_rejects_unknown_suffix():
    with pytest.raises(ValueError, match="unsupported RiceQuant code"):
        ricequant_to_ts_code("IF2403")
    with pytest.raises(ValueError, match="unsupported ts_code"):
        ts_code_to_ricequant("IF2403.CFFEX")


def _fake_rqdatac(monkeypatch, source_df):
    calls = {}
    fake_rqdatac = types.SimpleNamespace()

    def init(username, password):
        calls["init"] = (username, password)

    def get_price(**kwargs):
        calls["get_price"] = kwargs
        return source_df

    fake_rqdatac.init = init
    fake_rqdatac.get_price = get_price
    monkeypatch.setitem(sys.modules, "rqdatac", fake_rqdatac)
    return calls


def _source_minute_df():
    idx = pd.MultiIndex.from_tuples(
        [
            ("000001.XSHE", pd.Timestamp("2024-01-02 09:31:00")),
            ("000001.XSHE", pd.Timestamp("2024-01-02 09:32:00")),
        ],
        names=["order_book_id", "datetime"],
    )
    return pd.DataFrame(
        {
            "open": [10.0, 10.1],
            "close": [10.1, 10.2],
            "volume": [1000.0, 1200.0],
            "extra_vendor_field": ["a", "b"],
        },
        index=idx,
    )


def test_ricequant_fetcher_init_uses_username_password(monkeypatch):
    calls = _fake_rqdatac(monkeypatch, _source_minute_df())

    RiceQuantFetcher(username="user", password="password")

    assert calls["init"] == ("user", "password")


def test_ricequant_fetcher_init_uses_license_key(monkeypatch):
    calls = _fake_rqdatac(monkeypatch, _source_minute_df())

    RiceQuantFetcher(license_key="rq_license_key")

    assert calls["init"] == ("license", "rq_license_key")


def test_ricequant_fetcher_init_rejects_missing_or_ambiguous_credentials(monkeypatch):
    _fake_rqdatac(monkeypatch, _source_minute_df())

    with pytest.raises(ValueError, match="RiceQuant credentials"):
        RiceQuantFetcher()
    with pytest.raises(ValueError, match="RiceQuant credentials"):
        RiceQuantFetcher(username="user", password="password", license_key="rq_license_key")


def test_fetch_stock_minute_normalizes_multi_index(monkeypatch):
    calls = _fake_rqdatac(monkeypatch, _source_minute_df())

    fetcher = RiceQuantFetcher(username="user", password="password")
    df = fetcher.fetch_stock_minute(
        "000001.XSHE",
        "20240102",
        "20240102",
        adjust_type="none",
        skip_suspended=True,
    )

    assert calls["init"] == ("user", "password")
    assert calls["get_price"] == {
        "order_book_ids": "000001.XSHE",
        "start_date": "20240102",
        "end_date": "20240102",
        "frequency": "1m",
        "fields": None,
        "adjust_type": "none",
        "skip_suspended": True,
        "expect_df": True,
    }
    assert df.to_dict("records") == [
        {
            "order_book_id": "000001.XSHE",
            "datetime": pd.Timestamp("2024-01-02 09:31:00"),
            "open": 10.0,
            "close": 10.1,
            "volume": 1000.0,
            "extra_vendor_field": "a",
            "trade_date": "20240102",
            "ts_code": "000001.SZ",
        },
        {
            "order_book_id": "000001.XSHE",
            "datetime": pd.Timestamp("2024-01-02 09:32:00"),
            "open": 10.1,
            "close": 10.2,
            "volume": 1200.0,
            "extra_vendor_field": "b",
            "trade_date": "20240102",
            "ts_code": "000001.SZ",
        },
    ]


def test_fetch_stock_minute_empty_response_preserves_minimum_columns(monkeypatch):
    fake_rqdatac = types.SimpleNamespace(
        init=lambda username, password: None,
        get_price=lambda **kwargs: pd.DataFrame(),
    )
    monkeypatch.setitem(sys.modules, "rqdatac", fake_rqdatac)

    fetcher = RiceQuantFetcher(username="user", password="password")
    df = fetcher.fetch_stock_minute("000001.XSHE", "20240102", "20240102")

    assert df.empty
    assert list(df.columns) == ["order_book_id", "datetime", "trade_date", "ts_code"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_ricequant_fetcher.py tests/test_fetcher.py -q
```

Expected: import failure for `zer0share.sources.ricequant`.

- [ ] **Step 3: Move Tushare fetcher behind sources shim**

Create `zer0share/sources/tushare.py` by moving the full current contents of `zer0share/fetcher.py` into it.

Replace `zer0share/fetcher.py` with:

```python
from zer0share.sources.tushare import (
    CI_MEMBER_COLS,
    FUTURES_EXCHANGES,
    FUT_INDEX_CODES,
    INDEX_DAILY_CODES,
    OPTIONS_EXCHANGES,
    TushareFetcher,
    _select_columns_or_empty,
)

__all__ = [
    "CI_MEMBER_COLS",
    "FUTURES_EXCHANGES",
    "FUT_INDEX_CODES",
    "INDEX_DAILY_CODES",
    "OPTIONS_EXCHANGES",
    "TushareFetcher",
    "_select_columns_or_empty",
]
```

If tests import other constants from `zer0share.fetcher`, add them to this shim explicitly.

- [ ] **Step 4: Add RiceQuant source module**

Create `zer0share/sources/ricequant.py`:

```python
from __future__ import annotations

import importlib

import pandas as pd
from loguru import logger


def ts_code_to_ricequant(ts_code: str) -> str:
    if ts_code.endswith(".SZ"):
        return ts_code[:-3] + ".XSHE"
    if ts_code.endswith(".SH"):
        return ts_code[:-3] + ".XSHG"
    raise ValueError(f"unsupported ts_code for RiceQuant A-share minute data: {ts_code}")


def ricequant_to_ts_code(order_book_id: str) -> str:
    if order_book_id.endswith(".XSHE"):
        return order_book_id[:-5] + ".SZ"
    if order_book_id.endswith(".XSHG"):
        return order_book_id[:-5] + ".SH"
    raise ValueError(f"unsupported RiceQuant code for A-share minute data: {order_book_id}")


class RiceQuantFetcher:
    def __init__(
        self,
        username: str = "",
        password: str = "",
        license_key: str = "",
    ):
        try:
            rqdatac = importlib.import_module("rqdatac")
        except ImportError as exc:
            raise ImportError(
                "rqdatac is required for RiceQuant sync; install it or disable [ricequant].enabled"
            ) from exc
        has_user_password = bool(username or password)
        if license_key and has_user_password:
            raise ValueError("RiceQuant credentials must use either license_key or username/password, not both")
        if license_key:
            rqdatac.init(username="license", password=license_key)
        elif username and password:
            rqdatac.init(username=username, password=password)
        else:
            raise ValueError("RiceQuant credentials require license_key or both username and password")
        self._rqdatac = rqdatac

    def fetch_stock_minute(
        self,
        order_book_id: str,
        start_date: str,
        end_date: str,
        adjust_type: str = "none",
        skip_suspended: bool = True,
    ) -> pd.DataFrame:
        logger.debug(f"拉取 RiceQuant 股票分钟线: {order_book_id} {start_date}~{end_date}")
        df = self._rqdatac.get_price(
            order_book_ids=order_book_id,
            start_date=start_date,
            end_date=end_date,
            frequency="1m",
            fields=None,
            adjust_type=adjust_type,
            skip_suspended=skip_suspended,
            expect_df=True,
        )
        if df is None or df.empty:
            return pd.DataFrame(columns=["order_book_id", "datetime", "trade_date", "ts_code"])
        result = df.reset_index()
        if "order_book_id" not in result.columns:
            result.insert(0, "order_book_id", order_book_id)
        if "datetime" not in result.columns:
            raise ValueError("RiceQuant minute data must include datetime index or column")
        result["datetime"] = pd.to_datetime(result["datetime"])
        result["trade_date"] = result["datetime"].dt.strftime("%Y%m%d")
        result["ts_code"] = result["order_book_id"].map(ricequant_to_ts_code)
        return result
```

Create `zer0share/sources/__init__.py`:

```python
from dataclasses import dataclass

from zer0share.sources.ricequant import RiceQuantFetcher
from zer0share.sources.tushare import TushareFetcher


@dataclass(frozen=True)
class DataSources:
    tushare: TushareFetcher
    ricequant: RiceQuantFetcher | None = None


__all__ = ["DataSources", "RiceQuantFetcher", "TushareFetcher"]
```

- [ ] **Step 5: Run tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_ricequant_fetcher.py tests/test_fetcher.py -q
```

Expected: RiceQuant fetcher tests and existing Tushare fetcher tests pass.

- [ ] **Step 6: Commit**

```bash
git add zer0share/sources zer0share/fetcher.py tests/test_ricequant_fetcher.py tests/test_fetcher.py
git commit -m "feat: add ricequant source adapter"
```

## Task 3: Pipeline Source Wiring

**Files:**
- Modify: `zer0share/pipeline.py`
- Modify: `zer0share/cli.py`
- Modify: `zer0share/scheduler.py`
- Test: `tests/test_pipeline.py`
- Test: `tests/test_cli.py`
- Test: `tests/test_scheduler.py`

- [ ] **Step 1: Write failing wiring tests**

In `tests/test_pipeline.py`, change the `pipeline` fixture to pass `DataSources(tushare=fetcher)` after importing `DataSources`:

```python
from zer0share.sources import DataSources
```

```python
@pytest.fixture
def pipeline(cfg, fetcher, notifier):
    return Pipeline(cfg, DataSources(tushare=fetcher), notifier)
```

Add:

```python
def test_pipeline_accepts_data_sources_container(cfg, fetcher, notifier):
    sources = DataSources(tushare=fetcher)
    pipeline = Pipeline(cfg, sources, notifier)
    assert "daily_kline" in pipeline.registry
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_pipeline.py -q
```

Expected: `Pipeline` fails because it still expects a fetcher, not `DataSources`.

- [ ] **Step 3: Update Pipeline**

Modify `zer0share/pipeline.py`:

```python
from zer0share.sources import DataSources
```

Change constructor:

```python
class Pipeline:
    def __init__(self, cfg: Config, sources: DataSources, notifier: Notifier):
        meta = MetaStore(cfg.db_path)
        calendar = TradingCalendar(meta)
        self._runtime = SyncRuntime(calendar=calendar, notifier=notifier, meta=meta)
        self._registry: dict[str, SyncJob] = {}
        self._build_registry(cfg, sources)

    def _build_registry(self, cfg: Config, sources: DataSources) -> None:
        from zer0share.sync import calendar, stock, index, industry, futures, options, ricequant
        for module in [calendar, stock, index, industry, futures, options]:
            for job in module.build_jobs(cfg, sources.tushare):
                self._registry[job.table_name] = job
        for job in ricequant.build_jobs(cfg, sources):
            self._registry[job.table_name] = job
```

Create temporary `zer0share/sync/ricequant.py` so imports pass before Task 4:

```python
from zer0share.sources import DataSources


def build_jobs(cfg, sources: DataSources):
    return []
```

- [ ] **Step 4: Update CLI and scheduler construction**

Modify `zer0share/cli.py` imports:

```python
from zer0share.sources import DataSources, RiceQuantFetcher, TushareFetcher
```

Replace `_make_pipeline` body:

```python
def _make_pipeline(config_path: str = "config/settings.toml") -> Pipeline:
    cfg = load_config(Path(config_path))
    init_logger(cfg.log_path)
    sources = DataSources(
        tushare=TushareFetcher(cfg.tushare_token),
        ricequant=(
            RiceQuantFetcher(
                username=cfg.ricequant.username,
                password=cfg.ricequant.password,
                license_key=cfg.ricequant.license_key,
            )
            if cfg.ricequant.enabled
            else None
        ),
    )
    notifier = Notifier(cfg.wecom_webhook_url, cfg.notifier_enabled)
    return Pipeline(cfg, sources, notifier)
```

Modify `zer0share/scheduler.py` imports:

```python
from zer0share.sources import DataSources, RiceQuantFetcher, TushareFetcher
```

Replace the fetcher construction in `start_scheduler` with:

```python
sources = DataSources(
    tushare=TushareFetcher(cfg.tushare_token),
    ricequant=(
        RiceQuantFetcher(
            username=cfg.ricequant.username,
            password=cfg.ricequant.password,
            license_key=cfg.ricequant.license_key,
        )
        if cfg.ricequant.enabled
        else None
    ),
)
notifier = Notifier(cfg.wecom_webhook_url, cfg.notifier_enabled)

with Pipeline(cfg, sources, notifier) as pipeline:
    scheduler = BlockingScheduler()
```

- [ ] **Step 5: Run pipeline and CLI/scheduler tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_pipeline.py tests/test_cli.py tests/test_scheduler.py -q
```

Expected: tests pass with no RiceQuant jobs registered yet.

- [ ] **Step 6: Commit**

```bash
git add zer0share/pipeline.py zer0share/cli.py zer0share/scheduler.py zer0share/sync/ricequant.py tests/test_pipeline.py tests/test_cli.py tests/test_scheduler.py
git commit -m "refactor: wire pipeline through data sources"
```

## Task 4: RiceQuant Minute Sync Job

**Files:**
- Modify: `zer0share/sync/ricequant.py`
- Modify: `zer0share/cli.py`
- Test: `tests/test_ricequant_sync.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write failing sync tests**

Create `tests/test_ricequant_sync.py`:

```python
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from zer0share.pipeline import Pipeline
from zer0share.sources import DataSources
from zer0share.storage import DailyPartitionStore, SnapshotStore, write_trade_cal


@pytest.fixture
def cfg(tmp_path):
    c = MagicMock()
    c.data_dir = tmp_path
    c.db_path = tmp_path / "meta.duckdb"
    c.ricequant.enabled = True
    c.ricequant.request_sleep_seconds = 0.0
    c.ricequant.adjust_type = "none"
    c.ricequant.skip_suspended = True
    return c


def _write_basic(data_dir):
    SnapshotStore(data_dir / "stock" / "basic" / "data.parquet").write(
        pd.DataFrame(
            {
                "ts_code": ["000001.SZ", "600000.SH", "000002.SZ"],
                "symbol": ["000001", "600000", "000002"],
                "name": ["Ping An", "SPDB", "Vanke"],
                "area": ["Shenzhen", "Shanghai", "Shenzhen"],
                "industry": ["Bank", "Bank", "Real Estate"],
                "fullname": ["Ping An Bank", "SPDB", "Vanke"],
                "enname": ["Ping An", "SPDB", "Vanke"],
                "cnspell": ["payh", "pfyh", "wka"],
                "market": ["Main Board", "Main Board", "Main Board"],
                "exchange": ["SZSE", "SSE", "SZSE"],
                "curr_type": ["CNY", "CNY", "CNY"],
                "list_status": ["L", "L", "D"],
                "list_date": ["19910403", "19991110", "19910129"],
                "delist_date": [None, None, "20200101"],
                "is_hs": ["S", "H", None],
                "act_name": ["a", "b", "c"],
                "act_ent_type": ["x", "y", "z"],
            }
        )
    )


def _setup_calendar(pipeline, cfg):
    write_trade_cal(
        cfg.data_dir,
        "SSE",
        pd.DataFrame(
            {
                "exchange": ["SSE"],
                "cal_date": ["20240102"],
                "is_open": [True],
                "pretrade_date": ["20231229"],
            }
        ),
    )
    pipeline._runtime.calendar.load_from_parquet(cfg.data_dir)
    pipeline._runtime.meta.update_last_date("trade_cal", "20240102")
    pipeline._runtime.calendar._today_fn = lambda: "20240102"


def _minute_df(order_book_id):
    return pd.DataFrame(
        {
            "order_book_id": [order_book_id],
            "datetime": [pd.Timestamp("2024-01-02 09:31:00")],
            "open": [10.0],
            "close": [10.1],
            "trade_date": ["20240102"],
            "ts_code": ["000001.SZ" if order_book_id.endswith("XSHE") else "600000.SH"],
        }
    )


def test_ricequant_stock_minute_registered_when_enabled(cfg):
    tushare = MagicMock()
    ricequant = MagicMock()

    pipeline = Pipeline(cfg, DataSources(tushare=tushare, ricequant=ricequant), MagicMock())

    assert "ricequant_stock_minute" in pipeline.registry


def test_ricequant_stock_minute_requires_enabled_source(cfg):
    cfg.ricequant.enabled = False
    pipeline = Pipeline(cfg, DataSources(tushare=MagicMock(), ricequant=None), MagicMock())

    assert "ricequant_stock_minute" not in pipeline.registry


def test_ricequant_stock_minute_sync_writes_daily_partition(cfg):
    _write_basic(cfg.data_dir)
    ricequant = MagicMock()
    ricequant.fetch_stock_minute.side_effect = [
        _minute_df("000001.XSHE"),
        _minute_df("600000.XSHG"),
    ]
    pipeline = Pipeline(cfg, DataSources(tushare=MagicMock(), ricequant=ricequant), MagicMock())
    _setup_calendar(pipeline, cfg)

    with patch("zer0share.sync.ricequant.time.sleep"):
        pipeline.run("ricequant_stock_minute", start_date="20240102", end_date="20240102")

    result = DailyPartitionStore(cfg.data_dir / "ricequant" / "stock_minute").read("20240102")
    assert result["order_book_id"].tolist() == ["000001.XSHE", "600000.XSHG"]
    assert pipeline._runtime.meta.get_last_date("ricequant_stock_minute") == "20240102"
    ricequant.fetch_stock_minute.assert_any_call("000001.XSHE", "20240102", "20240102", "none", True)
    ricequant.fetch_stock_minute.assert_any_call("600000.XSHG", "20240102", "20240102", "none", True)


def test_ricequant_stock_minute_partial_failures_write_successes(cfg):
    _write_basic(cfg.data_dir)
    ricequant = MagicMock()
    ricequant.fetch_stock_minute.side_effect = [
        RuntimeError("temporary rq error"),
        _minute_df("600000.XSHG"),
    ]
    notifier = MagicMock()
    pipeline = Pipeline(cfg, DataSources(tushare=MagicMock(), ricequant=ricequant), notifier)
    _setup_calendar(pipeline, cfg)

    with patch("zer0share.sync.ricequant.time.sleep"):
        pipeline.run("ricequant_stock_minute", start_date="20240102", end_date="20240102")

    result = DailyPartitionStore(cfg.data_dir / "ricequant" / "stock_minute").read("20240102")
    assert result["order_book_id"].tolist() == ["600000.XSHG"]
    assert pipeline._runtime.meta.get_last_date("ricequant_stock_minute") == "20240102"
    assert notifier.send.called


def test_ricequant_stock_minute_all_failures_do_not_advance_meta(cfg):
    _write_basic(cfg.data_dir)
    ricequant = MagicMock()
    ricequant.fetch_stock_minute.side_effect = RuntimeError("rq unavailable")
    pipeline = Pipeline(cfg, DataSources(tushare=MagicMock(), ricequant=ricequant), MagicMock())
    _setup_calendar(pipeline, cfg)

    with patch("zer0share.sync.ricequant.time.sleep"):
        with pytest.raises(RuntimeError, match="all RiceQuant stock minute fetches failed"):
            pipeline.run("ricequant_stock_minute", start_date="20240102", end_date="20240102")

    assert pipeline._runtime.meta.get_last_date("ricequant_stock_minute") is None
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_ricequant_sync.py -q
```

Expected: tests fail because `ricequant_stock_minute` is not implemented.

- [ ] **Step 3: Implement sync job**

Replace `zer0share/sync/ricequant.py` with:

```python
import time

import pandas as pd
from loguru import logger

import zer0share.dateutil as dateutil
from zer0share.sources import DataSources
from zer0share.sources.ricequant import ts_code_to_ricequant
from zer0share.storage import DailyPartitionStore, SnapshotStore
from zer0share.sync._jobs import SyncJob, _format_duration


TABLE_NAME = "ricequant_stock_minute"


class RiceQuantStockMinuteSyncJob(SyncJob):
    table_name = TABLE_NAME
    supports_date_range = True

    def __init__(self, cfg, fetcher):
        self.cfg = cfg
        self.fetcher = fetcher
        self.store = DailyPartitionStore(cfg.data_dir / "ricequant" / "stock_minute")

    def _load_active_ts_codes(self) -> list[str]:
        df = SnapshotStore(self.cfg.data_dir / "stock" / "basic" / "data.parquet").read()
        if df.empty:
            raise FileNotFoundError("stock basic data not found; run `python main.py sync --table basic` first")
        active = df[df["list_status"] == "L"]
        return sorted(active["ts_code"].dropna().astype(str).tolist())

    def run(self, rt, start_date: str | None = None, end_date: str | None = None) -> None:
        today = rt.calendar.today()
        if start_date is None:
            last = rt.meta.get_last_date(TABLE_NAME)
            start = dateutil.add_days(last, 1) if last is not None else today
            end = today
        else:
            start = start_date
            end = end_date if end_date is not None else today
        if start > end:
            raise ValueError(f"start_date {start} is after end_date {end}")

        trading_days = rt.calendar.get_trading_days("SSE", start, end)
        if not trading_days and rt.meta.get_last_date("trade_cal") is None:
            raise RuntimeError("No trading days found. Run `sync --table trade_cal` first.")

        ts_codes = self._load_active_ts_codes()
        current_meta = rt.meta.get_last_date(TABLE_NAME)
        for trade_date in trading_days:
            if self.store.exists(trade_date):
                if current_meta is None or trade_date > current_meta:
                    rt.meta.update_last_date(TABLE_NAME, trade_date)
                    current_meta = trade_date
                continue

            frames = []
            failures = []
            started = time.monotonic()
            for ts_code in ts_codes:
                order_book_id = ts_code_to_ricequant(ts_code)
                try:
                    df = self.fetcher.fetch_stock_minute(
                        order_book_id,
                        trade_date,
                        trade_date,
                        self.cfg.ricequant.adjust_type,
                        self.cfg.ricequant.skip_suspended,
                    )
                except Exception as exc:
                    failures.append((order_book_id, str(exc)))
                    logger.warning(f"{TABLE_NAME}: {order_book_id} failed on {trade_date}: {exc}")
                    continue
                if df is not None and not df.empty:
                    frames.append(df)
                time.sleep(self.cfg.ricequant.request_sleep_seconds)

            if not frames:
                raise RuntimeError(f"all RiceQuant stock minute fetches failed for {trade_date}; failures={failures[:5]}")

            combined = pd.concat(frames, ignore_index=True)
            self.store.write(trade_date, combined)
            rt.meta.update_last_date(TABLE_NAME, trade_date)
            current_meta = trade_date
            elapsed = _format_duration(time.monotonic() - started)
            message = (
                f"{TABLE_NAME} 同步完成\n"
                f"日期：{trade_date}｜写入 {len(combined)} 行｜失败 {len(failures)}｜耗时 {elapsed}"
            )
            if failures:
                message += "\n失败样例：" + "; ".join(f"{code}: {err}" for code, err in failures[:5])
            rt.notifier.send(message)


def build_jobs(cfg, sources: DataSources):
    if not cfg.ricequant.enabled:
        return []
    if sources.ricequant is None:
        raise RuntimeError("RiceQuant is enabled but RiceQuantFetcher is not configured")
    return [RiceQuantStockMinuteSyncJob(cfg, sources.ricequant)]
```

- [ ] **Step 4: Add CLI table group**

Modify `zer0share/cli.py`:

```python
RICEQUANT_TABLES = [
    "ricequant_stock_minute",
]

SYNC_TABLES = [
    *STOCK_TABLES,
    *FUTURES_TABLES,
    *OPTIONS_TABLES,
    *RICEQUANT_TABLES,
]
```

Add click option:

```python
@click.option("--ricequant", "sync_ricequant", is_flag=True, default=False)
```

Add function argument `sync_ricequant: bool`.

Add branch before `elif table is not None`:

```python
elif sync_ricequant:
    for t in RICEQUANT_TABLES:
        pipeline.run(t, start_date=start_date, end_date=end_date)
```

Update final error text to include `--ricequant`.

- [ ] **Step 5: Run tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_ricequant_sync.py tests/test_pipeline.py tests/test_cli.py -q
```

Expected: sync tests pass, and existing pipeline/CLI tests pass after updating expected table counts where needed.

- [ ] **Step 6: Commit**

```bash
git add zer0share/sync/ricequant.py zer0share/cli.py tests/test_ricequant_sync.py tests/test_pipeline.py tests/test_cli.py
git commit -m "feat: sync ricequant stock minute data"
```

## Task 5: Local rq_api Query Layer

**Files:**
- Create: `zer0share/query/ricequant.py`
- Create: `zer0share/rq_api.py`
- Modify: `zer0share/__init__.py`
- Test: `tests/test_rq_api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing rq_api tests**

Create `tests/test_rq_api.py`:

```python
import pandas as pd
import pytest

from zer0share import rq_api
from zer0share.rq_api import RQLocal
from zer0share.storage import DailyPartitionStore


def _write_minute(data_dir, trade_date="20240102"):
    DailyPartitionStore(data_dir / "ricequant" / "stock_minute").write(
        trade_date,
        pd.DataFrame(
            {
                "order_book_id": ["000001.XSHE", "600000.XSHG"],
                "datetime": [pd.Timestamp("2024-01-02 09:31:00"), pd.Timestamp("2024-01-02 09:31:00")],
                "open": [10.0, 20.0],
                "close": [10.1, 20.1],
                "volume": [1000.0, 2000.0],
                "extra_vendor_field": ["a", "b"],
                "trade_date": ["20240102", "20240102"],
                "ts_code": ["000001.SZ", "600000.SH"],
            }
        ),
    )


def test_rq_api_exported():
    assert callable(rq_api)


def test_get_price_filters_single_order_book_id(tmp_path):
    _write_minute(tmp_path)
    rq = RQLocal(tmp_path)

    result = rq.get_price(
        "000001.XSHE",
        start_date="20240102",
        end_date="20240102",
        frequency="1m",
        fields=["order_book_id", "datetime", "close", "extra_vendor_field"],
    )

    assert result.to_dict("records") == [
        {
            "order_book_id": "000001.XSHE",
            "datetime": pd.Timestamp("2024-01-02 09:31:00"),
            "close": 10.1,
            "extra_vendor_field": "a",
        }
    ]


def test_get_price_filters_multiple_order_book_ids(tmp_path):
    _write_minute(tmp_path)
    rq = RQLocal(tmp_path)

    result = rq.get_price(
        ["600000.XSHG", "000001.XSHE"],
        start_date="20240102",
        end_date="20240102",
        frequency="1m",
        fields="order_book_id,ts_code,close",
    )

    assert result.to_dict("records") == [
        {"order_book_id": "000001.XSHE", "ts_code": "000001.SZ", "close": 10.1},
        {"order_book_id": "600000.XSHG", "ts_code": "600000.SH", "close": 20.1},
    ]


def test_get_price_select_star_preserves_vendor_fields(tmp_path):
    _write_minute(tmp_path)
    rq = RQLocal(tmp_path)

    result = rq.get_price("000001.XSHE", start_date="20240102", end_date="20240102")

    assert "extra_vendor_field" in result.columns


def test_get_price_rejects_unsupported_options(tmp_path):
    rq = RQLocal(tmp_path)

    with pytest.raises(NotImplementedError, match="frequency"):
        rq.get_price("000001.XSHE", frequency="5m")
    with pytest.raises(NotImplementedError, match="market"):
        rq.get_price("000001.XSHE", market="hk")
    with pytest.raises(NotImplementedError, match="expect_df"):
        rq.get_price("000001.XSHE", expect_df=False)
    with pytest.raises(NotImplementedError, match="time_slice"):
        rq.get_price("000001.XSHE", time_slice="09:31-10:00")
    with pytest.raises(ValueError, match="adjust_type"):
        rq.get_price("000001.XSHE", adjust_type="pre")


def test_get_price_missing_data_raises_sync_hint(tmp_path):
    rq = RQLocal(tmp_path)

    with pytest.raises(FileNotFoundError, match="sync --table ricequant_stock_minute"):
        rq.get_price("000001.XSHE", start_date="20240102", end_date="20240102")
```

Add to `tests/test_api.py`:

```python
def test_pro_api_query_does_not_dispatch_ricequant_table(tmp_path):
    pro = LocalPro(tmp_path)
    with pytest.raises(ValueError, match="unknown api"):
        pro.query("ricequant_stock_minute")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_rq_api.py tests/test_api.py::test_pro_api_query_does_not_dispatch_ricequant_table -q
```

Expected: `zer0share.rq_api` import fails.

- [ ] **Step 3: Implement RiceQuant query module**

Create `zer0share/query/ricequant.py`:

```python
from pathlib import Path

import duckdb
import pandas as pd

from zer0share.query import QueryContext
from zer0share.query.repository import SqlFilter, date_range_filters, in_filter


TABLE_COLUMNS = [
    "order_book_id",
    "datetime",
    "open",
    "close",
    "high",
    "low",
    "limit_up",
    "limit_down",
    "total_turnover",
    "volume",
    "num_trades",
    "prev_close",
    "trade_date",
    "ts_code",
]


def _parse_fields(fields):
    if fields is None:
        return None
    if isinstance(fields, str):
        return [item.strip() for item in fields.split(",") if item.strip()]
    return list(fields)


def _source(ctx: QueryContext) -> Path:
    return ctx.data_dir / "ricequant" / "stock_minute" / "date=*" / "data.parquet"


def _ensure_exists(ctx: QueryContext) -> None:
    table_dir = ctx.data_dir / "ricequant" / "stock_minute"
    if not table_dir.exists():
        raise FileNotFoundError(
            "ricequant_stock_minute data not found; run `python main.py sync --table ricequant_stock_minute` first"
        )


def get_price(
    ctx: QueryContext,
    order_book_ids,
    start_date=None,
    end_date=None,
    fields=None,
    limit: int | None = None,
    offset: int | None = None,
) -> pd.DataFrame:
    _ensure_exists(ctx)
    parsed_fields = _parse_fields(fields)
    selected = "*" if parsed_fields is None else ", ".join(parsed_fields)
    filters: list[SqlFilter] = []
    if order_book_ids is not None:
        filters.append(in_filter("order_book_id", order_book_ids, TABLE_COLUMNS))
    filters.extend(date_range_filters("trade_date", None, start_date, end_date, TABLE_COLUMNS))

    sql = f"SELECT {selected} FROM read_parquet(?, hive_partitioning=true, union_by_name=true)"
    params: list[object] = [str(_source(ctx))]
    if filters:
        sql += " WHERE " + " AND ".join(f.clause for f in filters)
        for filt in filters:
            params.extend(filt.params)
    sql += " ORDER BY order_book_id, datetime"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    if offset is not None:
        sql += " OFFSET ?"
        params.append(offset)
    return duckdb.connect().execute(sql, params).fetchdf()
```

- [ ] **Step 4: Implement rq_api entrypoint**

Create `zer0share/rq_api.py`:

```python
import datetime as dt
from pathlib import Path

from zer0share.config import load_config
from zer0share.query import QueryContext
from zer0share.query import ricequant


def _check_date(value):
    if value is None:
        return
    try:
        dt.datetime.strptime(value, "%Y%m%d")
    except ValueError as exc:
        raise ValueError(f"invalid date format: {value!r}; expected YYYYMMDD") from exc


class RQLocal:
    def __init__(self, data_dir):
        self._ctx = QueryContext(Path(data_dir))

    def get_price(
        self,
        order_book_ids,
        start_date=None,
        end_date=None,
        frequency="1m",
        fields=None,
        adjust_type="none",
        skip_suspended=None,
        expect_df=True,
        time_slice=None,
        market="cn",
        limit=None,
        offset=None,
    ):
        if frequency != "1m":
            raise NotImplementedError("local rq_api.get_price currently only supports frequency='1m'")
        if market != "cn":
            raise NotImplementedError("local rq_api.get_price currently only supports market='cn'")
        if expect_df is not True:
            raise NotImplementedError("local rq_api.get_price currently only supports expect_df=True")
        if time_slice is not None:
            raise NotImplementedError("local rq_api.get_price does not support time_slice yet")
        if adjust_type != "none":
            raise ValueError("adjust_type must be 'none' for local RiceQuant minute data")
        _check_date(start_date)
        _check_date(end_date)
        if start_date is not None and end_date is not None and end_date < start_date:
            raise ValueError("end_date must be on or after start_date")
        return ricequant.get_price(
            self._ctx,
            order_book_ids=order_book_ids,
            start_date=start_date,
            end_date=end_date,
            fields=fields,
            limit=limit,
            offset=offset,
        )


def rq_api(config_path="config/settings.toml") -> RQLocal:
    cfg = load_config(Path(config_path))
    return RQLocal(cfg.data_dir)
```

Modify `zer0share/__init__.py`:

```python
from zer0share.api import LocalPro, pro_api
from zer0share.rq_api import RQLocal, rq_api

__all__ = ["LocalPro", "RQLocal", "pro_api", "rq_api"]
```

- [ ] **Step 5: Run tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_rq_api.py tests/test_api.py -q
```

Expected: RiceQuant query tests pass and Tushare local API tests still pass.

- [ ] **Step 6: Commit**

```bash
git add zer0share/query/ricequant.py zer0share/rq_api.py zer0share/__init__.py tests/test_rq_api.py tests/test_api.py
git commit -m "feat: add local ricequant query api"
```

## Task 6: Documentation And Final Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/SYNC_GUIDE.md`
- Modify: `skills/zer0share-data/references/api.md`

- [ ] **Step 1: Update README**

Add a RiceQuant subsection near sync commands:

~~~markdown
### RiceQuant 分钟线（私有分支）

RiceQuant 数据源通过独立入口同步和查询，不混入 `pro_api()`。

认证支持 license key 或用户名/密码二选一：

```toml
[ricequant]
enabled = true
license_key = "your_ricequant_license_key"
```

或：

```toml
[ricequant]
enabled = true
username = "your_username"
password = "your_password"
```

```bash
uv run python main.py sync --table ricequant_stock_minute --start-date 20240102 --end-date 20240102
```

本地查询：

```python
from zer0share import rq_api

rq = rq_api()
df = rq.get_price(
    "000001.XSHE",
    start_date="20240102",
    end_date="20240102",
    frequency="1m",
)
```
~~~

- [ ] **Step 2: Update sync guide and skill API reference**

Add to `docs/SYNC_GUIDE.md`:

~~~markdown
## RiceQuant 私有数据源

`ricequant_stock_minute` 需要 `[ricequant].enabled = true`，并配置 RiceQuant `license_key` 或 `username/password`。同步前需要先完成 `basic` 和 `trade_cal`：

```bash
uv run python main.py sync --table basic
uv run python main.py sync --table trade_cal
uv run python main.py sync --table ricequant_stock_minute --start-date 20240102 --end-date 20240102
```
~~~

Add to `skills/zer0share-data/references/api.md`:

~~~markdown
## RiceQuant local API

- `rq_api().get_price(order_book_ids, start_date=None, end_date=None, frequency="1m", fields=None, limit=None, offset=None)`
  - Local sync table: `ricequant_stock_minute`
  - Storage: `data/ricequant/stock_minute/date=YYYYMMDD/data.parquet`
  - First private implementation supports A-share 1-minute bars only.
~~~

- [ ] **Step 3: Run focused test suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider tests/test_config.py tests/test_ricequant_fetcher.py tests/test_ricequant_sync.py tests/test_rq_api.py tests/test_pipeline.py tests/test_cli.py tests/test_scheduler.py tests/test_api.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Run full test suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider -q
```

Expected: full suite passes. If `rqdatac` cannot be installed in the current environment, verify that tests use fake modules and do not import real `rqdatac`.

- [ ] **Step 5: Commit docs**

```bash
git add README.md docs/SYNC_GUIDE.md skills/zer0share-data/references/api.md
git commit -m "docs: document ricequant private data source"
```

- [ ] **Step 6: Optional real account smoke test**

Run only in an environment with valid RiceQuant credentials in `config/settings.toml`:

```bash
uv run python main.py sync --table ricequant_stock_minute --start-date 20240102 --end-date 20240102
uv run python -c "from zer0share import rq_api; print(rq_api().get_price('000001.XSHE', start_date='20240102', end_date='20240102', frequency='1m').head())"
```

Expected: first command writes `data/ricequant/stock_minute/date=20240102/data.parquet`; second command prints minute bars for `000001.XSHE`.

## Self-Review Notes

- Spec coverage: config, optional `rqdatac`, data source adapter, private sync table, independent storage path, `rq_api()` query, `pro_api()` isolation, docs, and tests are covered.
- Scope: this plan implements only A-share 1-minute bars. Tick, realtime websocket, resampling, and local minute adjustment remain out of scope.
- Type consistency: sync table name is consistently `ricequant_stock_minute`; storage path is consistently `data/ricequant/stock_minute`; public local query entrypoint is consistently `rq_api().get_price(order_book_ids, frequency="1m")`.
