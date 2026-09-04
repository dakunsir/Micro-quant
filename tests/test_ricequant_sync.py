from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from microshare.pipeline import Pipeline
from microshare.sources import DataSources
from microshare.storage import DailyPartitionStore, SnapshotStore, write_trade_cal


@pytest.fixture
def cfg(tmp_path):
    c = MagicMock()
    c.data_dir = tmp_path
    c.db_path = tmp_path / "meta.duckdb"
    c.ricequant.enabled = True
    c.ricequant.stock_minute.request_sleep_seconds = 0.0
    c.ricequant.stock_minute.batch_size = 2
    c.ricequant.stock_minute.adjust_type = "none"
    c.ricequant.stock_minute.skip_suspended = True
    return c


def _write_basic(data_dir):
    SnapshotStore(data_dir / "ricequant" / "basic" / "data.parquet").write(
        pd.DataFrame(
            {
                "order_book_id": ["000001.XSHE", "600000.XSHG", "000002.XSHE"],
                "symbol": ["平安银行", "浦发银行", "万科A"],
                "status": ["Active", "Active", "Delisted"],
                "vendor_extra": ["a", "b", "c"],
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


def _minute_df(order_book_ids):
    if isinstance(order_book_ids, str):
        order_book_ids = [order_book_ids]
    return pd.DataFrame(
        {
            "order_book_id": order_book_ids,
            "datetime": [pd.Timestamp("2024-01-02 09:31:00")] * len(order_book_ids),
            "open": [10.0] * len(order_book_ids),
            "close": [10.1] * len(order_book_ids),
            "trade_date": ["20240102"] * len(order_book_ids),
        }
    )


def test_ricequant_stock_minute_registered_when_enabled(cfg):
    tushare = MagicMock()
    ricequant = MagicMock()

    pipeline = Pipeline(cfg, DataSources(tushare=tushare, ricequant=ricequant), MagicMock())

    assert "ricequant_stock_minute" in pipeline.registry


def test_ricequant_basic_registered_when_enabled(cfg):
    pipeline = Pipeline(cfg, DataSources(tushare=MagicMock(), ricequant=MagicMock()), MagicMock())

    assert "ricequant_basic" in pipeline.registry


def test_ricequant_stock_minute_requires_enabled_source(cfg):
    cfg.ricequant.enabled = False
    pipeline = Pipeline(cfg, DataSources(tushare=MagicMock(), ricequant=None), MagicMock())

    assert "ricequant_stock_minute" not in pipeline.registry
    assert "ricequant_basic" not in pipeline.registry


def test_ricequant_basic_sync_writes_snapshot(cfg):
    ricequant = MagicMock()
    ricequant.fetch_basic.return_value = pd.DataFrame(
        {
            "order_book_id": ["000001.XSHE"],
            "symbol": ["平安银行"],
            "vendor_extra": ["a"],
        }
    )
    pipeline = Pipeline(cfg, DataSources(tushare=MagicMock(), ricequant=ricequant), MagicMock())
    pipeline._runtime.calendar._today_fn = lambda: "20240102"

    pipeline.run("ricequant_basic")

    result = SnapshotStore(cfg.data_dir / "ricequant" / "basic" / "data.parquet").read()
    assert result.to_dict("records") == [
        {"order_book_id": "000001.XSHE", "symbol": "平安银行", "vendor_extra": "a"}
    ]
    assert pipeline._runtime.meta.get_last_date("ricequant_basic") == "20240102"


def test_ricequant_stock_minute_sync_writes_daily_partition(cfg):
    _write_basic(cfg.data_dir)
    ricequant = MagicMock()
    ricequant.fetch_stock_minute.side_effect = lambda order_book_ids, *_: _minute_df(order_book_ids)
    pipeline = Pipeline(cfg, DataSources(tushare=MagicMock(), ricequant=ricequant), MagicMock())
    _setup_calendar(pipeline, cfg)

    with patch("microshare.sync.ricequant.time.sleep"):
        pipeline.run("ricequant_stock_minute", start_date="20240102", end_date="20240102")

    result = DailyPartitionStore(cfg.data_dir / "ricequant" / "stock_minute").read("20240102")
    assert result["order_book_id"].tolist() == ["000001.XSHE", "600000.XSHG"]
    assert pipeline._runtime.meta.get_last_date("ricequant_stock_minute") == "20240102"
    ricequant.fetch_stock_minute.assert_called_once_with(
        ["000001.XSHE", "600000.XSHG"], "20240102", "20240102", "none", True
    )


def test_ricequant_stock_minute_partial_failures_write_successes(cfg):
    _write_basic(cfg.data_dir)
    ricequant = MagicMock()
    ricequant.fetch_stock_minute.side_effect = [
        RuntimeError("temporary rq error"),
        _minute_df(["600000.XSHG"]),
    ]
    cfg.ricequant.stock_minute.batch_size = 1
    notifier = MagicMock()
    pipeline = Pipeline(cfg, DataSources(tushare=MagicMock(), ricequant=ricequant), notifier)
    _setup_calendar(pipeline, cfg)

    with patch("microshare.sync.ricequant.time.sleep"):
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

    with patch("microshare.sync.ricequant.time.sleep"):
        with pytest.raises(RuntimeError, match="all RiceQuant stock minute fetches failed"):
            pipeline.run("ricequant_stock_minute", start_date="20240102", end_date="20240102")

    assert pipeline._runtime.meta.get_last_date("ricequant_stock_minute") is None
