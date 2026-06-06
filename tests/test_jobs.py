import time
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest
from zer0share.storage import MetaStore, DailyPartitionStore, SnapshotStore
from zer0share.trading_calendar import TradingCalendar
from zer0share.sync import SyncRuntime
from zer0share.sync._jobs import DailySyncJob, SnapshotSyncJob, FIRST_DATE
from zer0share.catalog import DAILY_KLINE_SPEC, BASIC_SPEC
import pyarrow as pa
import pyarrow.parquet as pq


def _write_trade_cal_fixture(data_dir, exchange, df):
    cal_dir = data_dir / "trade_cal" / f"exchange={exchange}"
    cal_dir.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), cal_dir / "data.parquet")


def _make_runtime(tmp_path, today: str = "20240102"):
    meta = MetaStore(tmp_path / "meta.duckdb")
    cal_df = pd.DataFrame({
        "exchange": ["SSE", "SSE", "SSE"],
        "cal_date": ["20240102", "20240103", "20240104"],
        "is_open": [True, False, True],
        "pretrade_date": ["20231229", "20240102", "20240102"],
    })
    _write_trade_cal_fixture(tmp_path, "SSE", cal_df)
    cal = TradingCalendar(meta, today_fn=lambda: today)
    cal.load_from_parquet(tmp_path, ["SSE"])
    meta.update_last_date("trade_cal", "20240104")
    notifier = MagicMock()
    return SyncRuntime(calendar=cal, notifier=notifier, meta=meta), meta


def test_daily_sync_job_writes_partition(tmp_path):
    rt, meta = _make_runtime(tmp_path)
    store = DailyPartitionStore(tmp_path / "daily_kline")
    fetch = MagicMock(return_value=pd.DataFrame({
        "ts_code": ["000001.SZ"], "trade_date": ["20240102"],
    }))
    job = DailySyncJob(table_name="daily_kline", spec=DAILY_KLINE_SPEC, fetch=fetch, store=store)
    meta.update_last_date("daily_kline", "20240101")

    with patch("zer0share.sync._jobs.time") as mock_time:
        job.run(rt)

    assert store.exists("20240102")
    # 20240103 is not a trading day, 20240104 is but today is 20240102 so no 20240104
    assert meta.get_last_date("daily_kline") == "20240102"
    meta.close()


def test_daily_sync_job_skips_existing_partition(tmp_path):
    rt, meta = _make_runtime(tmp_path)
    store = DailyPartitionStore(tmp_path / "daily_kline")
    store.write("20240102", pd.DataFrame({"ts_code": ["000001.SZ"]}))
    fetch = MagicMock(return_value=pd.DataFrame())
    job = DailySyncJob(table_name="daily_kline", spec=DAILY_KLINE_SPEC, fetch=fetch, store=store)
    meta.update_last_date("daily_kline", "20240101")

    with patch("zer0share.sync._jobs.time"):
        job.run(rt)

    fetch.assert_not_called()
    meta.close()


def test_daily_sync_job_already_up_to_date(tmp_path):
    rt, meta = _make_runtime(tmp_path)
    store = DailyPartitionStore(tmp_path / "daily_kline")
    fetch = MagicMock()
    job = DailySyncJob(table_name="daily_kline", spec=DAILY_KLINE_SPEC, fetch=fetch, store=store)
    meta.update_last_date("daily_kline", "20240102")

    job.run(rt)

    fetch.assert_not_called()
    meta.close()


def test_daily_sync_job_raises_on_fetch_error(tmp_path):
    rt, meta = _make_runtime(tmp_path)
    store = DailyPartitionStore(tmp_path / "daily_kline")
    fetch = MagicMock(side_effect=RuntimeError("API error"))
    job = DailySyncJob(table_name="daily_kline", spec=DAILY_KLINE_SPEC, fetch=fetch, store=store)
    meta.update_last_date("daily_kline", "20240101")

    with patch("zer0share.sync._jobs.time"), pytest.raises(RuntimeError):
        job.run(rt)

    rt.notifier.send.assert_called_once()
    meta.close()


def test_snapshot_sync_job_writes_file(tmp_path):
    rt, meta = _make_runtime(tmp_path)
    store = SnapshotStore(tmp_path / "basic" / "data.parquet")
    fetch = MagicMock(return_value=pd.DataFrame({"ts_code": ["000001.SZ"]}))
    job = SnapshotSyncJob(table_name="basic", spec=BASIC_SPEC, fetch=fetch, store=store, skip_non_trading=False)

    job.run(rt)

    assert store.read().iloc[0]["ts_code"] == "000001.SZ"
    assert meta.get_last_date("basic") == "20240102"
    meta.close()


def test_snapshot_sync_job_skips_non_trading(tmp_path):
    # 20240103 is not a trading day in our fixture
    rt, meta = _make_runtime(tmp_path, today="20240103")
    store = SnapshotStore(tmp_path / "basic" / "data.parquet")
    fetch = MagicMock()
    job = SnapshotSyncJob(table_name="basic", spec=BASIC_SPEC, fetch=fetch, store=store, skip_non_trading=True)

    job.run(rt)

    fetch.assert_not_called()
    meta.close()
