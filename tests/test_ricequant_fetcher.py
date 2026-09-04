import sys
import types

import pandas as pd
import pytest

from microshare.sources.ricequant import (
    RiceQuantFetcher,
)


def _fake_rqdatac(monkeypatch, source_df):
    calls = {}
    fake_rqdatac = types.SimpleNamespace()

    def init(username, password):
        calls["init"] = (username, password)

    def get_price(**kwargs):
        calls["get_price"] = kwargs
        return source_df

    def all_instruments(**kwargs):
        calls["all_instruments"] = kwargs
        return pd.DataFrame(
            {
                "order_book_id": ["000001.XSHE", "600000.XSHG"],
                "symbol": ["平安银行", "浦发银行"],
                "status": ["Active", "Active"],
                "vendor_extra": ["a", "b"],
            }
        )

    fake_rqdatac.init = init
    fake_rqdatac.get_price = get_price
    fake_rqdatac.all_instruments = all_instruments
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

    fetcher = RiceQuantFetcher(username="user", password="password")
    assert "init" not in calls  # 构造时不连接，首次拉取才连接

    fetcher.fetch_stock_minute("000001.XSHE", "20240102", "20240102")

    assert calls["init"] == ("user", "password")


def test_ricequant_fetcher_init_uses_license_key(monkeypatch):
    calls = _fake_rqdatac(monkeypatch, _source_minute_df())

    fetcher = RiceQuantFetcher(license_key="rq_license_key")
    assert "init" not in calls  # 构造时不连接，首次拉取才连接

    fetcher.fetch_stock_minute("000001.XSHE", "20240102", "20240102")

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
        },
        {
            "order_book_id": "000001.XSHE",
            "datetime": pd.Timestamp("2024-01-02 09:32:00"),
            "open": 10.1,
            "close": 10.2,
            "volume": 1200.0,
            "extra_vendor_field": "b",
            "trade_date": "20240102",
        },
    ]


def test_fetch_basic_uses_all_instruments_and_preserves_columns(monkeypatch):
    calls = _fake_rqdatac(monkeypatch, _source_minute_df())
    fetcher = RiceQuantFetcher(username="user", password="password")

    df = fetcher.fetch_basic()

    assert calls["all_instruments"] == {"type": "CS", "market": "cn"}
    assert df.to_dict("records") == [
        {
            "order_book_id": "000001.XSHE",
            "symbol": "平安银行",
            "status": "Active",
            "vendor_extra": "a",
        },
        {
            "order_book_id": "600000.XSHG",
            "symbol": "浦发银行",
            "status": "Active",
            "vendor_extra": "b",
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
    assert list(df.columns) == ["order_book_id", "datetime", "trade_date"]
