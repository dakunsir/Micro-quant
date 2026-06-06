import pandas as pd
import pytest
from zer0share.storage import MetaStore, write_trade_cal
from zer0share.trading_calendar import TradingCalendar
from zer0share.sync import SyncRuntime


@pytest.fixture
def cal(tmp_path):
    meta = MetaStore(tmp_path / "meta.duckdb")
    df = pd.DataFrame({
        "exchange": ["SSE", "SSE", "SSE"],
        "cal_date": ["20240102", "20240103", "20240104"],
        "is_open": [True, False, True],
        "pretrade_date": ["20231229", "20240102", "20240102"],
    })
    write_trade_cal(tmp_path, "SSE", df)
    c = TradingCalendar(meta)
    c.load_from_parquet(tmp_path, ["SSE"])
    yield c
    meta.close()


def test_today_default_returns_string(cal):
    result = cal.today()
    assert len(result) == 8 and result.isdigit()


def test_today_injectable(tmp_path):
    meta = MetaStore(tmp_path / "meta.duckdb")
    cal = TradingCalendar(meta, today_fn=lambda: "20240105")
    assert cal.today() == "20240105"
    meta.close()


def test_get_trading_days(cal):
    days = cal.get_trading_days("SSE", "20240101", "20240104")
    assert days == ["20240102", "20240104"]


def test_is_trading_day_open(cal):
    assert cal.is_trading_day("SSE", "20240102") is True


def test_is_trading_day_closed(cal):
    assert cal.is_trading_day("SSE", "20240103") is False


def test_is_trading_day_unknown_returns_true(cal):
    # A date not in calendar at all should return True (don't block if uncertain)
    assert cal.is_trading_day("SSE", "20251225") is True


def test_skip_if_not_trading_on_closed_day(cal):
    cal2 = TradingCalendar(cal._meta, today_fn=lambda: "20240103")
    assert cal2.skip_if_not_trading("SSE") is True


def test_skip_if_not_trading_on_open_day(cal):
    cal2 = TradingCalendar(cal._meta, today_fn=lambda: "20240102")
    assert cal2.skip_if_not_trading("SSE") is False


def test_ensure_loaded_raises_when_trade_cal_missing(tmp_path):
    meta = MetaStore(tmp_path / "meta.duckdb")
    cal = TradingCalendar(meta)
    from unittest.mock import MagicMock
    rt = SyncRuntime(calendar=cal, notifier=MagicMock(), meta=meta)
    with pytest.raises(RuntimeError, match="交易日历未加载"):
        cal.ensure_loaded(rt)
    meta.close()
