import pandas as pd
import pytest

from microshare import rq_api
from microshare.rq_api import RQLocal
from microshare.storage import DailyPartitionStore


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
            }
        ),
    )


def _write_basic(data_dir):
    from microshare.storage import SnapshotStore

    SnapshotStore(data_dir / "ricequant" / "basic" / "data.parquet").write(
        pd.DataFrame(
            {
                "order_book_id": ["000001.XSHE", "600000.XSHG"],
                "symbol": ["平安银行", "浦发银行"],
                "type": ["CS", "CS"],
                "market": ["cn", "cn"],
                "status": ["Active", "Active"],
                "vendor_extra": ["a", "b"],
            }
        )
    )


def test_rq_api_exported():
    assert callable(rq_api)


def test_all_instruments_filters_type_market_and_fields(tmp_path):
    _write_basic(tmp_path)
    rq = RQLocal(tmp_path)

    result = rq.all_instruments(type="CS", market="cn", fields="order_book_id,symbol,vendor_extra")

    assert result.to_dict("records") == [
        {"order_book_id": "000001.XSHE", "symbol": "平安银行", "vendor_extra": "a"},
        {"order_book_id": "600000.XSHG", "symbol": "浦发银行", "vendor_extra": "b"},
    ]


def test_all_instruments_rejects_date_filter_for_snapshot(tmp_path):
    _write_basic(tmp_path)
    rq = RQLocal(tmp_path)

    with pytest.raises(NotImplementedError, match="date"):
        rq.all_instruments(type="CS", date="20240102")


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
        fields="order_book_id,trade_date,close",
    )

    assert result.to_dict("records") == [
        {"order_book_id": "000001.XSHE", "trade_date": "20240102", "close": 10.1},
        {"order_book_id": "600000.XSHG", "trade_date": "20240102", "close": 20.1},
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
