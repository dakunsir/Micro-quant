import pandas as pd
import pytest

from microshare.storage import (
    MetaStore,
    read_trade_cal,
    write_trade_cal,
)


@pytest.fixture
def store(tmp_path):
    s = MetaStore(tmp_path / "meta.duckdb")
    yield s
    s.close()


def test_init_creates_table(store):
    assert store.get_last_date("daily_kline") is None


def test_update_and_get_last_date(store):
    store.update_last_date("daily_kline", "20240115")
    assert store.get_last_date("daily_kline") == "20240115"


def test_update_overwrites_previous(store):
    store.update_last_date("daily_kline", "20240101")
    store.update_last_date("daily_kline", "20240131")
    assert store.get_last_date("daily_kline") == "20240131"


def test_different_table_names_are_independent(store):
    store.update_last_date("daily_kline", "20240110")
    store.update_last_date("basic", "20240220")
    assert store.get_last_date("daily_kline") == "20240110"
    assert store.get_last_date("basic") == "20240220"


def test_context_manager(tmp_path):
    with MetaStore(tmp_path / "meta.duckdb") as store:
        store.update_last_date("daily_kline", "20240101")
        assert store.get_last_date("daily_kline") == "20240101"


def test_write_and_read_trade_cal(tmp_path):
    df = pd.DataFrame({
        "exchange": ["SSE", "SSE"],
        "cal_date": ["20240102", "20240103"],
        "is_open": [True, False],
        "pretrade_date": ["20231229", "20240102"],
    })
    write_trade_cal(tmp_path, "SSE", df)
    result = read_trade_cal(tmp_path, "SSE")
    assert len(result) == 2
    assert (tmp_path / "stock" / "trade_cal" / "exchange=SSE" / "data.parquet").exists()


def test_read_trade_cal_returns_empty_if_not_exists(tmp_path):
    result = read_trade_cal(tmp_path, "SSE")
    assert result.empty


def test_load_trade_cal_from_parquet(tmp_path):
    db_path = tmp_path / "meta.duckdb"
    df = pd.DataFrame({
        "exchange": ["SSE", "SSE"],
        "cal_date": ["20240102", "20240103"],
        "is_open": [True, False],
        "pretrade_date": ["20231229", "20240102"],
    })
    write_trade_cal(tmp_path, "SSE", df)
    with MetaStore(db_path) as store:
        store.load_trade_cal_from_parquet(tmp_path)
        row = store._conn.execute(
            "SELECT COUNT(*) FROM trade_cal WHERE exchange='SSE'"
        ).fetchone()
        assert row[0] == 2


def test_load_trade_cal_from_parquet_filters_exchanges(tmp_path):
    db_path = tmp_path / "meta.duckdb"
    sse_df = pd.DataFrame({
        "exchange": ["SSE"],
        "cal_date": ["20240102"],
        "is_open": [True],
        "pretrade_date": ["20231229"],
    })
    cffex_df = pd.DataFrame({
        "exchange": ["CFFEX"],
        "cal_date": ["20240102"],
        "is_open": [True],
        "pretrade_date": ["20231229"],
    })
    write_trade_cal(tmp_path, "SSE", sse_df)
    write_trade_cal(tmp_path, "CFFEX", cffex_df)
    with MetaStore(db_path) as store:
        store.load_trade_cal_from_parquet(tmp_path, ["SSE"])
        exchanges = store._conn.execute(
            "SELECT DISTINCT exchange FROM trade_cal"
        ).fetchall()
    assert exchanges == [("SSE",)]


def test_get_trading_days(tmp_path):
    db_path = tmp_path / "meta.duckdb"
    df = pd.DataFrame({
        "exchange": ["SSE"] * 5,
        "cal_date": [
            "20240102", "20240103", "20240104", "20240105", "20240106",
        ],
        "is_open": [True, False, True, False, True],
        "pretrade_date": [
            "20231229", "20240102", "20240102", "20240104", "20240104",
        ],
    })
    write_trade_cal(tmp_path, "SSE", df)
    with MetaStore(db_path) as store:
        store.load_trade_cal_from_parquet(tmp_path)
        days = store.get_trading_days("SSE", "20240101", "20240106")
    assert days == ["20240102", "20240104", "20240106"]


def test_get_trading_days_returns_empty_when_no_cal(tmp_path):
    db_path = tmp_path / "meta.duckdb"
    with MetaStore(db_path) as store:
        days = store.get_trading_days("SSE", "20240101", "20240106")
    assert days == []


def test_get_trading_days_exchange_isolation(tmp_path):
    db_path = tmp_path / "meta.duckdb"
    sse_df = pd.DataFrame({
        "exchange": ["SSE"],
        "cal_date": ["20240102"],
        "is_open": [True],
        "pretrade_date": ["20231229"],
    })
    szse_df = pd.DataFrame({
        "exchange": ["SZSE"],
        "cal_date": ["20240103"],
        "is_open": [True],
        "pretrade_date": ["20240102"],
    })
    write_trade_cal(tmp_path, "SSE", sse_df)
    write_trade_cal(tmp_path, "SZSE", szse_df)
    with MetaStore(db_path) as store:
        store.load_trade_cal_from_parquet(tmp_path)
        sse_days = store.get_trading_days("SSE", "20240101", "20240106")
        szse_days = store.get_trading_days("SZSE", "20240101", "20240106")
    assert sse_days == ["20240102"]
    assert szse_days == ["20240103"]


def test_is_trading_day_returns_true_for_open_day(tmp_path):
    db_path = tmp_path / "meta.duckdb"
    df = pd.DataFrame({
        "exchange": ["SSE"],
        "cal_date": ["20240102"],
        "is_open": [True],
        "pretrade_date": ["20231229"],
    })
    write_trade_cal(tmp_path, "SSE", df)
    with MetaStore(db_path) as store:
        store.load_trade_cal_from_parquet(tmp_path)
        assert store.is_trading_day("SSE", "20240102") is True


def test_is_trading_day_returns_false_for_closed_day(tmp_path):
    db_path = tmp_path / "meta.duckdb"
    df = pd.DataFrame({
        "exchange": ["SSE"],
        "cal_date": ["20240103"],
        "is_open": [False],
        "pretrade_date": ["20240102"],
    })
    write_trade_cal(tmp_path, "SSE", df)
    with MetaStore(db_path) as store:
        store.load_trade_cal_from_parquet(tmp_path)
        assert store.is_trading_day("SSE", "20240103") is False


def test_is_trading_day_returns_true_when_date_not_in_calendar(tmp_path):
    db_path = tmp_path / "meta.duckdb"
    df = pd.DataFrame({
        "exchange": ["SSE"],
        "cal_date": ["20240102"],
        "is_open": [True],
        "pretrade_date": ["20231229"],
    })
    write_trade_cal(tmp_path, "SSE", df)
    with MetaStore(db_path) as store:
        store.load_trade_cal_from_parquet(tmp_path)
        # 2024-01-10 is not in the calendar — conservative default True
        assert store.is_trading_day("SSE", "20240110") is True


def test_is_trading_day_returns_true_when_no_calendar_loaded(tmp_path):
    db_path = tmp_path / "meta.duckdb"
    with MetaStore(db_path) as store:
        assert store.is_trading_day("SSE", "20240102") is True


def test_daily_partition_store_write_and_exists(tmp_path):
    from microshare.storage import DailyPartitionStore

    store = DailyPartitionStore(tmp_path / "daily_kline")
    df = pd.DataFrame({"ts_code": ["000001.SZ"], "trade_date": ["20240102"]})
    assert store.exists("20240102") is False
    store.write("20240102", df)
    assert store.exists("20240102") is True
    assert (tmp_path / "daily_kline" / "date=20240102" / "data.parquet").exists()


def test_daily_partition_store_read(tmp_path):
    from microshare.storage import DailyPartitionStore

    store = DailyPartitionStore(tmp_path / "daily_kline")
    df = pd.DataFrame({"ts_code": ["000001.SZ"], "trade_date": ["20240102"]})
    store.write("20240102", df)
    result = store.read("20240102")
    assert len(result) == 1
    assert result.iloc[0]["ts_code"] == "000001.SZ"


def test_daily_partition_store_read_missing_returns_empty(tmp_path):
    from microshare.storage import DailyPartitionStore

    store = DailyPartitionStore(tmp_path / "daily_kline")
    assert store.read("20240102").empty


def test_snapshot_store_write_and_read(tmp_path):
    from microshare.storage import SnapshotStore

    store = SnapshotStore(tmp_path / "basic" / "data.parquet")
    df = pd.DataFrame({"ts_code": ["000001.SZ"], "name": ["平安银行"]})
    store.write(df)
    result = store.read()
    assert len(result) == 1
    assert result.iloc[0]["name"] == "平安银行"


def test_snapshot_store_read_missing_returns_empty(tmp_path):
    from microshare.storage import SnapshotStore

    store = SnapshotStore(tmp_path / "basic" / "data.parquet")
    assert store.read().empty


def test_index_weight_store_write_and_exists(tmp_path):
    from microshare.storage import IndexWeightStore

    store = IndexWeightStore(tmp_path / "index_weight")
    df = pd.DataFrame({"index_code": ["399300.SZ"], "con_code": ["000001.SZ"], "weight": [1.0]})
    assert store.exists("399300.SZ", "20240102") is False
    store.write("399300.SZ", "20240102", df)
    assert store.exists("399300.SZ", "20240102") is True
    assert (tmp_path / "index_weight" / "index_code=399300.SZ" / "date=20240102" / "data.parquet").exists()
