import time
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest
from zer0share.storage import MetaStore, DailyPartitionStore, SnapshotStore
from zer0share.trading_calendar import TradingCalendar
from zer0share.sync import SyncRuntime
from zer0share.sync._jobs import DailySyncJob, SnapshotSyncJob, _format_duration
from zer0share.catalog import DAILY_KLINE_SPEC, BASIC_SPEC
from zer0share.query.repository import DailyTableSpec
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


def test_daily_sync_job_logs_start_range_and_trading_day_count(tmp_path):
    rt, meta = _make_runtime(tmp_path, today="20240104")
    store = DailyPartitionStore(tmp_path / "daily_kline")
    fetch = MagicMock(return_value=pd.DataFrame({
        "ts_code": ["000001.SZ"], "trade_date": ["20240102"],
    }))
    job = DailySyncJob(table_name="daily_kline", spec=DAILY_KLINE_SPEC, fetch=fetch, store=store)
    meta.update_last_date("daily_kline", "20240101")

    with (
        patch("zer0share.sync._jobs.time"),
        patch("zer0share.sync._jobs.logger.info") as log_info,
    ):
        job.run(rt)

    log_info.assert_any_call("daily_kline: start 20240102 ~ 20240104, trading_days=2")
    meta.close()


def test_format_duration_uses_hh_mm_ss():
    assert _format_duration(0) == "00:00:00"
    assert _format_duration(65) == "00:01:05"
    assert _format_duration(3661) == "01:01:01"


def test_daily_sync_job_progress_log_includes_elapsed_and_eta(tmp_path):
    rt, meta = _make_runtime(tmp_path, today="20240104")
    store = DailyPartitionStore(tmp_path / "daily_kline")
    fetch = MagicMock(return_value=pd.DataFrame({
        "ts_code": ["000001.SZ"], "trade_date": ["20240102"],
    }))
    job = DailySyncJob(table_name="daily_kline", spec=DAILY_KLINE_SPEC, fetch=fetch, store=store)
    meta.update_last_date("daily_kline", "20240101")

    with (
        patch("zer0share.sync._jobs.PROGRESS_INTERVAL", 1),
        patch("zer0share.sync._jobs.time.sleep"),
        patch("zer0share.sync._jobs.time.monotonic", side_effect=[0, 10, 20, 20]),
        patch("zer0share.sync._jobs.logger.info") as log_info,
    ):
        job.run(rt)

    log_info.assert_any_call(
        "daily_kline: progress 1/2 (50.0%) "
        "success=1 empty=0 skipped=0 elapsed=00:00:10 eta=00:00:10"
    )
    meta.close()


def test_daily_sync_job_starts_from_spec_first_date_when_never_synced(tmp_path):
    meta = MetaStore(tmp_path / "meta.duckdb")
    cal_df = pd.DataFrame({
        "exchange": ["SSE", "SSE"],
        "cal_date": ["20150209", "20150210"],
        "is_open": [True, True],
        "pretrade_date": ["20150206", "20150209"],
    })
    _write_trade_cal_fixture(tmp_path, "SSE", cal_df)
    cal = TradingCalendar(meta, today_fn=lambda: "20150210")
    cal.load_from_parquet(tmp_path, ["SSE"])
    meta.update_last_date("trade_cal", "20150210")
    rt = SyncRuntime(calendar=cal, notifier=MagicMock(), meta=meta)
    spec = DailyTableSpec(
        name="early_daily",
        path_parts=("early_daily",),
        columns=["ts_code", "trade_date"],
        parquet_pattern="date=*/data.parquet",
        sync_table="early_daily",
        order_by="ts_code, trade_date",
        first_date="20150209",
    )
    store = DailyPartitionStore(tmp_path / "early_daily")
    fetch = MagicMock(side_effect=lambda trade_date: pd.DataFrame({
        "ts_code": ["000001.SZ"], "trade_date": [trade_date],
    }))
    job = DailySyncJob(table_name=spec.name, spec=spec, fetch=fetch, store=store)

    with patch("zer0share.sync._jobs.time"):
        job.run(rt)

    assert fetch.call_args_list[0].args == ("20150209",)
    assert store.exists("20150209")
    assert store.exists("20150210")
    assert meta.get_last_date("early_daily") == "20150210"
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
