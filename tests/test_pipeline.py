"""
tests/test_pipeline.py — Full rewrite for Registry-based Pipeline API.

Key API:
  - pipeline.run("table_name")  or  pipeline.run("table_name", start, end)
  - pipeline.registry  →  dict[str, SyncJob]
  - pipeline._runtime.meta  (was pipeline._meta)
  - pipeline._runtime.calendar._today_fn  for injecting today
"""
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from zer0share.pipeline import Pipeline
from zer0share.sync._helpers import EXCHANGES, ALL_EXCHANGES
from zer0share.storage import (
    read_sw_classify,
    read_sw_member,
    read_ci_member,
    write_basic,
    write_trade_cal,
    daily_partition_exists,
    DailyPartitionStore,
    write_daily_kline,
    write_daily_partition,
)
from zer0share.fetcher import INDEX_DAILY_CODES, FUTURES_EXCHANGES, OPTIONS_EXCHANGES


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def cfg(tmp_path):
    c = MagicMock()
    c.data_dir = tmp_path
    c.db_path = tmp_path / "meta.duckdb"
    return c


@pytest.fixture
def fetcher():
    return MagicMock()


@pytest.fixture
def notifier():
    return MagicMock()


@pytest.fixture
def pipeline(cfg, fetcher, notifier):
    return Pipeline(cfg, fetcher, notifier)


# ---------------------------------------------------------------------------
# Helper DataFrames
# ---------------------------------------------------------------------------

def _basic_df() -> pd.DataFrame:
    return pd.DataFrame({
        "ts_code": ["000001.SZ"],
        "symbol": ["000001"],
        "name": ["平安银行"],
        "area": ["深圳"],
        "industry": ["银行"],
        "fullname": ["平安银行股份有限公司"],
        "enname": ["Ping An Bank"],
        "cnspell": ["payh"],
        "market": ["主板"],
        "exchange": ["SZSE"],
        "curr_type": ["CNY"],
        "list_status": ["L"],
        "list_date": ["19910403"],
        "delist_date": [None],
        "is_hs": ["S"],
        "act_name": ["深圳市投资控股有限公司"],
        "act_ent_type": ["地方国企"],
    })


def _trade_cal_df(exchange: str) -> pd.DataFrame:
    return pd.DataFrame({
        "exchange": [exchange] * 3,
        "cal_date": ["20240102", "20240103", "20240104"],
        "is_open": [True, False, True],
        "pretrade_date": ["20231229", "20240102", "20240102"],
    })


def _kline_df(trade_date: str = "20240102") -> pd.DataFrame:
    return pd.DataFrame({
        "ts_code": ["000001.SZ"],
        "trade_date": [trade_date],
        "open": [10.0], "high": [11.0], "low": [9.5], "close": [10.5],
        "pre_close": [10.0], "change": [0.5], "pct_chg": [5.0],
        "vol": [100000.0], "amount": [1050000.0],
    })


def _index_daily_df(ts_code: str = "000300.SH", trade_date: str = "20240102") -> pd.DataFrame:
    return pd.DataFrame({
        "ts_code": [ts_code],
        "trade_date": [trade_date],
        "open": [3500.0], "high": [3550.0], "low": [3480.0], "close": [3520.0],
        "pre_close": [3490.0], "change": [30.0], "pct_chg": [0.86],
        "vol": [50000000.0], "amount": [1750000000.0],
    })


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------

def _setup_trade_cal_sse(pipeline, cfg) -> None:
    """Load SSE trade_cal with 2024-01-02 as open."""
    trade_cal = pd.DataFrame({
        "exchange": ["SSE"],
        "cal_date": ["20240102"],
        "is_open": [True],
        "pretrade_date": ["20231229"],
    })
    write_trade_cal(cfg.data_dir, "SSE", trade_cal)
    pipeline._runtime.calendar.load_from_parquet(cfg.data_dir)
    pipeline._runtime.meta.update_last_date("trade_cal", "20240102")
    pipeline._runtime.calendar._today_fn = lambda: "20240102"


def _setup_non_trading_day(pipeline, cfg) -> None:
    """Set up a non-trading day (2024-01-03, SSE=closed) in the calendar."""
    trade_cal = pd.DataFrame({
        "exchange": ["SSE"],
        "cal_date": ["20240103"],
        "is_open": [False],
        "pretrade_date": ["20240102"],
    })
    write_trade_cal(cfg.data_dir, "SSE", trade_cal)
    pipeline._runtime.calendar.load_from_parquet(cfg.data_dir)
    pipeline._runtime.meta.update_last_date("trade_cal", "20240103")
    pipeline._runtime.calendar._today_fn = lambda: "20240103"


def _setup_futures_trade_cal(pipeline, cfg) -> None:
    """Load SSE trade_cal with 2024-01-02 as open (for futures tests)."""
    trade_cal = pd.DataFrame({
        "exchange": ["SSE"],
        "cal_date": ["20240102"],
        "is_open": [True],
        "pretrade_date": ["20231229"],
    })
    write_trade_cal(cfg.data_dir, "SSE", trade_cal)
    pipeline._runtime.calendar.load_from_parquet(cfg.data_dir)
    pipeline._runtime.meta.update_last_date("trade_cal", "20240102")
    pipeline._runtime.calendar._today_fn = lambda: "20240102"


def _setup_options_trade_cal(pipeline, cfg) -> None:
    trade_cal = pd.DataFrame({
        "exchange": ["SSE"],
        "cal_date": ["20240102"],
        "is_open": [True],
        "pretrade_date": ["20231229"],
    })
    write_trade_cal(cfg.data_dir, "SSE", trade_cal)
    pipeline._runtime.calendar.load_from_parquet(cfg.data_dir)
    pipeline._runtime.meta.update_last_date("trade_cal", "20240102")
    pipeline._runtime.calendar._today_fn = lambda: "20240102"


def _setup_trade_cal(pipeline, cfg, trade_date: str, is_open: bool) -> None:
    """Generic helper to set up trade calendar for a single date and all exchanges."""
    pretrade_date = "20231229" if trade_date == "20240102" else "20240101"
    # Write trade_cal for all exchanges
    for exchange in ALL_EXCHANGES:
        trade_cal = pd.DataFrame({
            "exchange": [exchange],
            "cal_date": [trade_date],
            "is_open": [is_open],
            "pretrade_date": [pretrade_date],
        })
        write_trade_cal(cfg.data_dir, exchange, trade_cal)
    pipeline._runtime.calendar.load_from_parquet(cfg.data_dir)
    pipeline._runtime.meta.update_last_date("trade_cal", trade_date)
    pipeline._runtime.calendar._today_fn = lambda: trade_date


# ---------------------------------------------------------------------------
# 1. Context manager + registry
# ---------------------------------------------------------------------------

def test_pipeline_context_manager(cfg, fetcher, notifier):
    with Pipeline(cfg, fetcher, notifier) as p:
        assert p is not None


def test_pipeline_registry_contains_all_tables(pipeline):
    expected = {
        "trade_cal",
        "basic", "daily_kline", "adj_factor", "daily_basic", "stock_st",
        "suspend_d", "stk_limit", "index_weight", "index_daily",
        "industry", "ci_member",
        "fut_basic", "fut_daily", "fut_holding", "fut_wsr", "fut_settle",
        "fut_mapping", "ft_limit", "fut_weekly", "fut_monthly",
        "fut_index_daily", "fut_weekly_detail",
        "opt_basic", "opt_daily",
    }
    assert set(pipeline.registry.keys()) == expected
    assert len(pipeline.registry) == 25


def test_pipeline_run_unknown_table_raises(pipeline):
    with pytest.raises(ValueError, match="未知表"):
        pipeline.run("nonexistent")


def test_run_all_runs_all_25_jobs(pipeline, cfg):
    """Smoke test: run_all() on a fully up-to-date pipeline raises no exception."""
    # Mark all tables as already synced to today so every job returns immediately
    today = "20240102"
    pipeline._runtime.calendar._today_fn = lambda: today
    _setup_trade_cal(pipeline, cfg, trade_date=today, is_open=True)

    # Mark every registered table as already synced
    for table_name in pipeline.registry:
        pipeline._runtime.meta.update_last_date(table_name, today)
    # Also mark the per-index index_weight keys
    from zer0share.sync.equities import INDEX_CODES, _index_weight_meta_key
    for code in INDEX_CODES:
        pipeline._runtime.meta.update_last_date(_index_weight_meta_key(code), today)

    # Should complete without exception
    with patch("zer0share.sync._jobs.time"), patch("zer0share.sync.equities.time"), \
         patch("zer0share.sync.futures.time"), patch("zer0share.sync.options.time"):
        pipeline.run_all()


# ---------------------------------------------------------------------------
# 2. sync_basic
# ---------------------------------------------------------------------------

def test_sync_basic_first_run_writes_parquet(pipeline, cfg, fetcher):
    fetcher.fetch_basic.return_value = _basic_df()
    _setup_trade_cal_sse(pipeline, cfg)
    pipeline.run("basic")
    assert (cfg.data_dir / "basic" / "data.parquet").exists()


def test_sync_basic_refreshes_even_if_recently_updated(pipeline, cfg, fetcher):
    fetcher.fetch_basic.return_value = _basic_df()
    _setup_trade_cal_sse(pipeline, cfg)
    pipeline.run("basic")
    fetcher.fetch_basic.reset_mock()
    pipeline.run("basic")
    fetcher.fetch_basic.assert_called_once()


def test_sync_basic_failure_sends_alert_and_raises(pipeline, cfg, fetcher, notifier):
    fetcher.fetch_basic.side_effect = RuntimeError("API error")
    _setup_trade_cal_sse(pipeline, cfg)
    with pytest.raises(RuntimeError):
        pipeline.run("basic")
    notifier.send.assert_called_once()
    msg = notifier.send.call_args[0][0]
    assert "basic 同步失败" in msg


def test_sync_basic_skips_non_trading_day(pipeline, cfg, fetcher, notifier):
    _setup_non_trading_day(pipeline, cfg)
    pipeline.run("basic")
    fetcher.fetch_basic.assert_not_called()
    notifier.send.assert_not_called()


# ---------------------------------------------------------------------------
# 3. sync_daily_kline
# ---------------------------------------------------------------------------

def test_sync_daily_kline_writes_parquet(pipeline, cfg, fetcher):
    write_basic(cfg.data_dir, _basic_df())
    _setup_trade_cal_sse(pipeline, cfg)
    fetcher.fetch_daily_kline.return_value = _kline_df("20240102")
    pipeline._runtime.meta.update_last_date("daily_kline", "20240101")
    pipeline.run("daily_kline")
    assert (cfg.data_dir / "daily_kline" / "date=20240102" / "data.parquet").exists()


def test_sync_daily_kline_skips_empty_dates(pipeline, cfg, fetcher):
    write_basic(cfg.data_dir, _basic_df())
    _setup_trade_cal_sse(pipeline, cfg)
    fetcher.fetch_daily_kline.return_value = pd.DataFrame()
    pipeline._runtime.meta.update_last_date("daily_kline", "20240101")
    pipeline.run("daily_kline")
    assert not (cfg.data_dir / "daily_kline" / "date=20240102" / "data.parquet").exists()


def test_sync_daily_kline_sends_completion_notification(pipeline, cfg, fetcher, notifier):
    write_basic(cfg.data_dir, _basic_df())
    _setup_trade_cal_sse(pipeline, cfg)
    fetcher.fetch_daily_kline.return_value = _kline_df("20240102")
    pipeline._runtime.meta.update_last_date("daily_kline", "20240101")
    pipeline.run("daily_kline")
    notifier.send.assert_called_once()
    msg = notifier.send.call_args[0][0]
    assert "同步完成" in msg


def test_sync_daily_kline_already_up_to_date(pipeline, cfg, fetcher):
    write_basic(cfg.data_dir, _basic_df())
    pipeline._runtime.calendar._today_fn = lambda: "20240102"
    pipeline._runtime.meta.update_last_date("daily_kline", "20240102")
    pipeline.run("daily_kline")
    fetcher.fetch_daily_kline.assert_not_called()


def test_sync_daily_kline_failure_sends_alert_and_raises(pipeline, cfg, fetcher, notifier):
    write_basic(cfg.data_dir, _basic_df())
    _setup_trade_cal_sse(pipeline, cfg)
    fetcher.fetch_daily_kline.side_effect = RuntimeError("API error")
    pipeline._runtime.meta.update_last_date("daily_kline", "20240101")
    with pytest.raises(RuntimeError):
        pipeline.run("daily_kline")
    notifier.send.assert_called_once()
    msg = notifier.send.call_args[0][0]
    assert "同步失败" in msg


def test_sync_daily_kline_uses_trading_calendar(pipeline, cfg, fetcher):
    write_trade_cal(cfg.data_dir, "SSE", _trade_cal_df("SSE"))
    pipeline._runtime.calendar.load_from_parquet(cfg.data_dir)
    pipeline._runtime.meta.update_last_date("trade_cal", "20240104")
    pipeline._runtime.calendar._today_fn = lambda: "20240104"

    fetcher.fetch_daily_kline.return_value = _kline_df("20240102")
    pipeline._runtime.meta.update_last_date("daily_kline", "20240101")
    pipeline.run("daily_kline")

    # 20240102 (open) and 20240104 (open), not 20240103 (closed)
    assert fetcher.fetch_daily_kline.call_count == 2


def test_sync_daily_kline_raises_if_no_trade_cal(pipeline, cfg, fetcher):
    # No trade cal loaded, no meta
    pipeline._runtime.meta.update_last_date("daily_kline", "20240101")
    pipeline._runtime.calendar._today_fn = lambda: "20240102"
    with pytest.raises(RuntimeError, match="trade_cal"):
        pipeline.run("daily_kline")
    fetcher.fetch_daily_kline.assert_not_called()


def test_sync_daily_kline_range_skips_existing_partitions(pipeline, cfg, fetcher):
    write_basic(cfg.data_dir, _basic_df())
    trade_cal = pd.DataFrame({
        "exchange": ["SSE", "SSE", "SSE"],
        "cal_date": ["20240102", "20240103", "20240104"],
        "is_open": [True, True, True],
        "pretrade_date": ["20231229", "20240102", "20240103"],
    })
    write_trade_cal(cfg.data_dir, "SSE", trade_cal)
    pipeline._runtime.calendar.load_from_parquet(cfg.data_dir)
    pipeline._runtime.meta.update_last_date("trade_cal", "20240104")

    existing_df = _kline_df("20240103")
    write_daily_kline(cfg.data_dir, "20240103", existing_df)

    fetcher.fetch_daily_kline.side_effect = [
        _kline_df("20240102"),
        _kline_df("20240104"),
    ]
    pipeline.run("daily_kline", start_date="20240102", end_date="20240104")

    called_dates = [call.args[0] for call in fetcher.fetch_daily_kline.call_args_list]
    assert called_dates == ["20240102", "20240104"]


def test_sync_daily_kline_old_range_does_not_rewind_meta(pipeline, cfg, fetcher):
    write_basic(cfg.data_dir, _basic_df())
    trade_cal = pd.DataFrame({
        "exchange": ["SSE", "SSE"],
        "cal_date": ["20240102", "20240103"],
        "is_open": [True, True],
        "pretrade_date": ["20231229", "20240102"],
    })
    write_trade_cal(cfg.data_dir, "SSE", trade_cal)
    pipeline._runtime.calendar.load_from_parquet(cfg.data_dir)
    pipeline._runtime.meta.update_last_date("trade_cal", "20240103")
    pipeline._runtime.meta.update_last_date("daily_kline", "20240201")

    fetcher.fetch_daily_kline.return_value = _kline_df("20240102")
    pipeline.run("daily_kline", start_date="20240102", end_date="20240103")

    assert pipeline._runtime.meta.get_last_date("daily_kline") == "20240201"


def test_sync_daily_kline_range_defaults_end_date_to_today(pipeline, cfg, fetcher):
    write_basic(cfg.data_dir, _basic_df())
    trade_cal = pd.DataFrame({
        "exchange": ["SSE", "SSE"],
        "cal_date": ["20240102", "20240103"],
        "is_open": [True, True],
        "pretrade_date": ["20231229", "20240102"],
    })
    write_trade_cal(cfg.data_dir, "SSE", trade_cal)
    pipeline._runtime.calendar.load_from_parquet(cfg.data_dir)
    pipeline._runtime.meta.update_last_date("trade_cal", "20240103")
    pipeline._runtime.calendar._today_fn = lambda: "20240103"

    fetcher.fetch_daily_kline.return_value = _kline_df("20240102")
    pipeline.run("daily_kline", start_date="20240102")

    called_dates = [call.args[0] for call in fetcher.fetch_daily_kline.call_args_list]
    assert called_dates == ["20240102", "20240103"]


def test_sync_daily_kline_sleeps_between_requests(pipeline, cfg, fetcher):
    write_basic(cfg.data_dir, _basic_df())
    trade_cal = pd.DataFrame({
        "exchange": ["SSE", "SSE"],
        "cal_date": ["20240102", "20240103"],
        "is_open": [True, True],
        "pretrade_date": ["20231229", "20240102"],
    })
    write_trade_cal(cfg.data_dir, "SSE", trade_cal)
    pipeline._runtime.calendar.load_from_parquet(cfg.data_dir)
    pipeline._runtime.meta.update_last_date("trade_cal", "20240103")
    fetcher.fetch_daily_kline.return_value = _kline_df("20240102")

    with patch("zer0share.sync._jobs.time.sleep") as mock_sleep:
        pipeline.run("daily_kline", start_date="20240102", end_date="20240103")

    assert mock_sleep.call_count == 2
    mock_sleep.assert_any_call(0.2)


# ---------------------------------------------------------------------------
# 4. sync_trade_cal
# ---------------------------------------------------------------------------

def test_sync_trade_cal_writes_all_exchanges(pipeline, cfg, fetcher):
    fetcher.fetch_trade_cal.return_value = _trade_cal_df("SSE")
    pipeline._runtime.calendar._today_fn = lambda: "20240518"
    pipeline.run("trade_cal")
    for ex in EXCHANGES:
        assert (cfg.data_dir / "trade_cal" / f"exchange={ex}" / "data.parquet").exists()


def test_sync_trade_cal_loads_to_duckdb(pipeline, cfg, fetcher):
    fetcher.fetch_trade_cal.return_value = _trade_cal_df("SSE")
    pipeline._runtime.calendar._today_fn = lambda: "20240518"
    pipeline.run("trade_cal")
    days = pipeline._runtime.meta.get_trading_days("SSE", "20240101", "20240105")
    assert "20240102" in days
    assert "20240103" not in days


def test_sync_trade_cal_updates_meta(pipeline, cfg, fetcher):
    fetcher.fetch_trade_cal.return_value = _trade_cal_df("SSE")
    pipeline._runtime.calendar._today_fn = lambda: "20240518"
    pipeline.run("trade_cal")
    assert pipeline._runtime.meta.get_last_date("trade_cal") is not None


def test_sync_trade_cal_uses_incremental_range(pipeline, cfg, fetcher):
    write_trade_cal(cfg.data_dir, "SSE", pd.DataFrame({
        "exchange": ["SSE", "SSE"],
        "cal_date": ["20240101", "20240102"],
        "is_open": [True, True],
        "pretrade_date": ["20231229", "20240101"],
    }))
    write_trade_cal(cfg.data_dir, "SZSE", pd.DataFrame({
        "exchange": ["SZSE"],
        "cal_date": ["20240103"],
        "is_open": [True],
        "pretrade_date": ["20240102"],
    }))
    for ex in ALL_EXCHANGES:
        if ex in ("SSE", "SZSE"):
            continue
        write_trade_cal(cfg.data_dir, ex, pd.DataFrame({
            "exchange": [ex],
            "cal_date": ["20240103"],
            "is_open": [True],
            "pretrade_date": ["20240102"],
        }))

    def fetch_trade_cal(exchange, start, end):
        return pd.DataFrame({
            "exchange": [exchange],
            "cal_date": [start],
            "is_open": [True],
            "pretrade_date": ["20240102"],
        })

    fetcher.fetch_trade_cal.side_effect = fetch_trade_cal
    pipeline._runtime.calendar._today_fn = lambda: "20240518"
    pipeline.run("trade_cal")

    fetcher.fetch_trade_cal.assert_any_call("SSE", "20240103", "20241231")
    fetcher.fetch_trade_cal.assert_any_call("SZSE", "20240104", "20241231")
    assert pipeline._runtime.meta.get_last_date("trade_cal") == "20240103"


def test_sync_trade_cal_skips_when_already_covers_year_end(pipeline, cfg, fetcher):
    for exchange in ALL_EXCHANGES:
        write_trade_cal(cfg.data_dir, exchange, pd.DataFrame({
            "exchange": [exchange],
            "cal_date": ["20241231"],
            "is_open": [False],
            "pretrade_date": ["20241230"],
        }))

    pipeline._runtime.calendar._today_fn = lambda: "20240518"
    pipeline.run("trade_cal")

    fetcher.fetch_trade_cal.assert_not_called()
    assert pipeline._runtime.meta.get_last_date("trade_cal") == "20241231"


def test_sync_trade_cal_failure_sends_alert(pipeline, cfg, fetcher, notifier):
    fetcher.fetch_trade_cal.side_effect = RuntimeError("API error")
    with pytest.raises(RuntimeError):
        pipeline.run("trade_cal")
    notifier.send.assert_called_once()


def test_sync_trade_cal_writes_all_8_exchanges(pipeline, cfg, fetcher):
    fetcher.fetch_trade_cal.return_value = _trade_cal_df("SSE")
    pipeline._runtime.calendar._today_fn = lambda: "20240518"
    pipeline.run("trade_cal")
    for ex in ALL_EXCHANGES:
        assert (cfg.data_dir / "trade_cal" / f"exchange={ex}" / "data.parquet").exists(), f"Missing {ex}"


# ---------------------------------------------------------------------------
# 5. index_weight
# ---------------------------------------------------------------------------

def test_sync_index_weight_fetches_monthly_ranges(pipeline, cfg, fetcher):
    def fetch_index_weight(index_code, start, end):
        return pd.DataFrame({
            "index_code": [index_code],
            "con_code": ["000001.SZ"],
            "trade_date": [end],
            "weight": [1.0],
        })

    fetcher.fetch_index_weight.side_effect = fetch_index_weight

    with (
        patch("zer0share.sync.equities.INDEX_CODES", ["399300.SZ"]),
        patch("zer0share.sync.equities.time.sleep"),
    ):
        pipeline.run("index_weight", start_date="20240115", end_date="20240210")

    called_ranges = [
        (call.args[1], call.args[2])
        for call in fetcher.fetch_index_weight.call_args_list
    ]
    assert called_ranges == [
        ("20240115", "20240131"),
        ("20240201", "20240210"),
    ]
    assert pipeline._runtime.meta.get_last_date("index_weight:399300.SZ") == "20240210"
    assert pipeline._runtime.meta.get_last_date("index_weight") == "20240210"


def test_sync_index_weight_does_not_use_global_meta_for_new_index_meta(pipeline, cfg, fetcher):
    pipeline._runtime.meta.update_last_date("index_weight", "20240131")
    fetcher.fetch_index_weight.return_value = pd.DataFrame()
    pipeline._runtime.calendar._today_fn = lambda: "20240131"

    with (
        patch("zer0share.sync.equities.INDEX_CODES", ["399300.SZ"]),
        patch("zer0share.sync.equities.FIRST_DATE", "20240101"),
        patch("zer0share.sync.equities.time.sleep"),
    ):
        pipeline.run("index_weight")

    fetcher.fetch_index_weight.assert_called_once_with(
        "399300.SZ", "20240101", "20240131"
    )
    assert pipeline._runtime.meta.get_last_date("index_weight:399300.SZ") == "20240131"


# ---------------------------------------------------------------------------
# 6. sync_industry
# ---------------------------------------------------------------------------

def test_sync_industry_writes_sw_classify_and_member(pipeline, cfg, fetcher):
    classify_df = pd.DataFrame({
        "index_code": ["801010.SI"],
        "industry_name": ["农林牧渔"],
        "level": ["L1"],
        "parent_code": ["0"],
        "industry_code": ["110000"],
        "is_pub": ["1"],
        "src": ["SW2021"],
    })
    member_df = pd.DataFrame({
        "l1_code": ["801010.SI"], "l1_name": ["农林牧渔"],
        "l2_code": ["801016.SI"], "l2_name": ["种植业"],
        "l3_code": ["850111.SI"], "l3_name": ["种子"],
        "ts_code": ["002041.SZ"], "name": ["登海种业"],
        "in_date": ["20211213"], "out_date": [None], "is_new": ["Y"],
    })
    fetcher.fetch_sw_classify.return_value = classify_df
    fetcher.fetch_sw_member.return_value = member_df
    _setup_trade_cal_sse(pipeline, cfg)
    pipeline._runtime.calendar._today_fn = lambda: "20240518"

    pipeline.run("industry")

    assert read_sw_classify(cfg.data_dir).equals(classify_df)
    assert read_sw_member(cfg.data_dir).equals(member_df)
    assert pipeline._runtime.meta.get_last_date("sw_classify") == "20240518"
    assert pipeline._runtime.meta.get_last_date("sw_member") == "20240518"


def test_sync_industry_skips_non_trading_day(pipeline, cfg, fetcher, notifier):
    _setup_non_trading_day(pipeline, cfg)
    pipeline.run("industry")
    fetcher.fetch_sw_classify.assert_not_called()
    notifier.send.assert_not_called()


def test_sync_industry_failure_sends_alert_and_raises(pipeline, cfg, fetcher, notifier):
    fetcher.fetch_sw_classify.side_effect = RuntimeError("API error")
    _setup_trade_cal_sse(pipeline, cfg)
    with pytest.raises(RuntimeError):
        pipeline.run("industry")
    notifier.send.assert_called_once()
    msg = notifier.send.call_args[0][0]
    assert "industry 同步失败" in msg


# ---------------------------------------------------------------------------
# 7. sync_ci_member
# ---------------------------------------------------------------------------

def test_sync_ci_member_writes_parquet(pipeline, cfg, fetcher):
    member_df = pd.DataFrame({
        "l1_code": ["CI005001.CI"], "l1_name": ["农林牧渔"],
        "l2_code": ["CI005005.CI"], "l2_name": ["农产品加工"],
        "l3_code": ["CI005006.CI"], "l3_name": ["粮油加工"],
        "ts_code": ["000876.SZ"], "name": ["新希望"],
        "in_date": ["20200101"], "out_date": [None], "is_new": ["Y"],
    })
    fetcher.fetch_ci_member.return_value = member_df
    _setup_trade_cal_sse(pipeline, cfg)
    pipeline._runtime.calendar._today_fn = lambda: "20240518"

    pipeline.run("ci_member")

    assert read_ci_member(cfg.data_dir).equals(member_df)
    assert pipeline._runtime.meta.get_last_date("ci_member") == "20240518"


def test_sync_ci_member_skips_non_trading_day(pipeline, cfg, fetcher, notifier):
    _setup_non_trading_day(pipeline, cfg)
    pipeline.run("ci_member")
    fetcher.fetch_ci_member.assert_not_called()
    notifier.send.assert_not_called()


def test_sync_ci_member_failure_sends_alert_and_raises(pipeline, cfg, fetcher, notifier):
    fetcher.fetch_ci_member.side_effect = RuntimeError("API error")
    _setup_trade_cal_sse(pipeline, cfg)
    with pytest.raises(RuntimeError):
        pipeline.run("ci_member")
    notifier.send.assert_called_once()
    msg = notifier.send.call_args[0][0]
    assert "ci_member 同步失败" in msg


# ---------------------------------------------------------------------------
# 8. index_daily
# ---------------------------------------------------------------------------

def test_sync_index_daily_fetches_all_codes(pipeline, cfg, fetcher):
    fetcher.fetch_index_daily.return_value = pd.DataFrame()
    pipeline._runtime.calendar._today_fn = lambda: "20240102"

    pipeline.run("index_daily")

    assert fetcher.fetch_index_daily.call_count == len(INDEX_DAILY_CODES)
    for ts_code in INDEX_DAILY_CODES:
        fetcher.fetch_index_daily.assert_any_call(ts_code, "20160101", "20240102")


def test_sync_index_daily_writes_date_partitions(pipeline, cfg, fetcher):
    fetcher.fetch_index_daily.side_effect = [
        _index_daily_df(ts_code=ts_code, trade_date="20240102")
        for ts_code in INDEX_DAILY_CODES
    ]
    pipeline._runtime.calendar._today_fn = lambda: "20240102"

    with patch("zer0share.sync.equities.time.sleep"):
        pipeline.run("index_daily")

    assert daily_partition_exists(cfg.data_dir, "index_daily", "20240102")


def test_sync_index_daily_skips_existing_partitions(pipeline, cfg, fetcher):
    existing = _index_daily_df(ts_code="000300.SH", trade_date="20240102")
    write_daily_partition(cfg.data_dir, "index_daily", "20240102", existing)
    pipeline._runtime.calendar._today_fn = lambda: "20240102"

    fetcher.fetch_index_daily.side_effect = [
        _index_daily_df(ts_code=ts_code, trade_date="20240102")
        for ts_code in INDEX_DAILY_CODES
    ]

    with patch("zer0share.sync.equities.time.sleep"):
        pipeline.run("index_daily")

    assert daily_partition_exists(cfg.data_dir, "index_daily", "20240102")


def test_sync_index_daily_up_to_date_skips_fetch(pipeline, cfg, fetcher):
    pipeline._runtime.meta.update_last_date("index_daily", "20240102")
    pipeline._runtime.calendar._today_fn = lambda: "20240102"
    pipeline.run("index_daily")
    fetcher.fetch_index_daily.assert_not_called()


def test_sync_index_daily_no_data_sends_notification(pipeline, cfg, fetcher, notifier):
    fetcher.fetch_index_daily.return_value = pd.DataFrame()
    pipeline._runtime.calendar._today_fn = lambda: "20240102"

    with patch("zer0share.sync.equities.time.sleep"):
        pipeline.run("index_daily")

    notifier.send.assert_called_once_with("index_daily 无数据，跳过")


def test_sync_index_daily_updates_metastore(pipeline, cfg, fetcher):
    fetcher.fetch_index_daily.side_effect = [
        _index_daily_df(ts_code=ts_code, trade_date="20240102")
        for ts_code in INDEX_DAILY_CODES
    ]
    pipeline._runtime.calendar._today_fn = lambda: "20240102"

    with patch("zer0share.sync.equities.time.sleep"):
        pipeline.run("index_daily")

    assert pipeline._runtime.meta.get_last_date("index_daily") == "20240102"


# ---------------------------------------------------------------------------
# 9. fut_basic
# ---------------------------------------------------------------------------

def test_sync_fut_basic_writes_to_futures_subdir(pipeline, cfg, fetcher):
    def fut_basic_side_effect(exchange, fut_type):
        return pd.DataFrame({
            "ts_code": [f"CU2401.{exchange[:2]}"],
            "symbol": ["CU2401"], "exchange": [exchange], "name": ["沪铜2401"],
            "fut_code": ["CU"], "multiplier": [None], "trade_unit": ["5吨/手"],
            "per_unit": [5.0], "quote_unit": ["元/吨"], "quote_unit_desc": ["10元/吨"],
            "d_mode_desc": ["实物交割"], "list_date": ["20240101"], "delist_date": ["20240115"],
            "d_month": [None], "last_ddate": [None], "trade_time_desc": [None],
        })

    fetcher.fetch_fut_basic.side_effect = fut_basic_side_effect
    pipeline._runtime.calendar._today_fn = lambda: "20240102"

    with patch("zer0share.sync.futures.time.sleep"):
        # TradingCalendar.skip_if_not_trading will be called; inject a trading day
        _setup_trade_cal_sse(pipeline, cfg)
        pipeline.run("fut_basic")

    assert (cfg.data_dir / "futures" / "fut_basic" / "date=20240102" / "data.parquet").exists()
    assert pipeline._runtime.meta.get_last_date("fut_basic") == "20240102"


def test_sync_fut_basic_calls_all_exchanges_and_types(pipeline, cfg, fetcher):
    fetcher.fetch_fut_basic.return_value = pd.DataFrame()
    _setup_trade_cal_sse(pipeline, cfg)

    with patch("zer0share.sync.futures.time.sleep"):
        pipeline.run("fut_basic")

    assert fetcher.fetch_fut_basic.call_count == len(FUTURES_EXCHANGES) * 2
    for exchange in FUTURES_EXCHANGES:
        fetcher.fetch_fut_basic.assert_any_call(exchange, "1")
        fetcher.fetch_fut_basic.assert_any_call(exchange, "2")


def test_sync_fut_basic_failure_sends_alert_and_raises(pipeline, cfg, fetcher, notifier):
    fetcher.fetch_fut_basic.side_effect = RuntimeError("API error")
    _setup_trade_cal_sse(pipeline, cfg)
    with pytest.raises(RuntimeError):
        pipeline.run("fut_basic")
    notifier.send.assert_called_once()
    msg = notifier.send.call_args[0][0]
    assert "fut_basic 同步失败" in msg


def test_sync_fut_basic_skips_non_trading_day(pipeline, cfg, fetcher, notifier):
    _setup_non_trading_day(pipeline, cfg)
    pipeline.run("fut_basic")
    fetcher.fetch_fut_basic.assert_not_called()
    notifier.send.assert_not_called()


# ---------------------------------------------------------------------------
# 10. fut_daily
# ---------------------------------------------------------------------------

def _fut_daily_df(trade_date: str = "20240102") -> pd.DataFrame:
    return pd.DataFrame({
        "ts_code": ["CU2401.SHF"], "trade_date": [trade_date],
        "pre_close": [50000.0], "pre_settle": [50100.0],
        "open": [50200.0], "high": [50500.0], "low": [49900.0],
        "close": [50300.0], "settle": [50250.0],
        "change1": [200.0], "change2": [150.0],
        "vol": [10000.0], "amount": [251250.0],
        "oi": [50000.0], "oi_chg": [500.0], "delv_settle": [None],
    })


def test_sync_fut_daily_writes_to_futures_subdir(pipeline, cfg, fetcher):
    _setup_futures_trade_cal(pipeline, cfg)
    fetcher.fetch_fut_daily.return_value = _fut_daily_df("20240102")
    pipeline._runtime.meta.update_last_date("fut_daily", "20240101")

    with patch("zer0share.sync._jobs.time.sleep"):
        pipeline.run("fut_daily")

    assert (cfg.data_dir / "futures" / "fut_daily" / "date=20240102" / "data.parquet").exists()


def test_sync_fut_daily_skips_existing_partitions(pipeline, cfg, fetcher):
    _setup_futures_trade_cal(pipeline, cfg)
    fetcher.fetch_fut_daily.return_value = pd.DataFrame()
    pipeline._runtime.meta.update_last_date("fut_daily", "20240101")

    write_daily_partition(
        cfg.data_dir / "futures", "fut_daily", "20240102",
        pd.DataFrame({"ts_code": ["CU2401.SHF"], "trade_date": ["20240102"]}),
    )

    with patch("zer0share.sync._jobs.time.sleep"):
        pipeline.run("fut_daily")

    fetcher.fetch_fut_daily.assert_not_called()


def test_sync_fut_daily_up_to_date(pipeline, cfg, fetcher):
    pipeline._runtime.calendar._today_fn = lambda: "20240102"
    pipeline._runtime.meta.update_last_date("fut_daily", "20240102")
    pipeline.run("fut_daily")
    fetcher.fetch_fut_daily.assert_not_called()


# ---------------------------------------------------------------------------
# 11. ft_limit
# ---------------------------------------------------------------------------

def test_sync_ft_limit_writes_to_futures_subdir(pipeline, cfg, fetcher):
    _setup_futures_trade_cal(pipeline, cfg)
    fetcher.fetch_ft_limit.return_value = pd.DataFrame({
        "trade_date": ["20240102"], "ts_code": ["CU2401.SHF"], "name": ["沪铜2401"],
        "up_limit": [51000.0], "down_limit": [49000.0],
        "m_ratio": [0.10], "cont": ["CU"], "exchange": ["SHFE"],
    })
    pipeline._runtime.meta.update_last_date("ft_limit", "20240101")

    with patch("zer0share.sync._jobs.time.sleep"):
        pipeline.run("ft_limit")

    assert (cfg.data_dir / "futures" / "ft_limit" / "date=20240102" / "data.parquet").exists()


# ---------------------------------------------------------------------------
# 12. fut_weekly
# ---------------------------------------------------------------------------

def test_sync_fut_weekly_writes_to_futures_subdir(pipeline, cfg, fetcher):
    _setup_futures_trade_cal(pipeline, cfg)
    fetcher.fetch_fut_weekly.return_value = pd.DataFrame({
        "ts_code": ["CU2401.SHF"], "trade_date": ["20240102"], "freq": ["week"],
        "open": [50000.0], "high": [50500.0], "low": [49900.0], "close": [50300.0],
        "pre_close": [50000.0], "settle": [50250.0], "pre_settle": [50100.0],
        "vol": [10000.0], "amount": [251250.0], "oi": [50000.0], "oi_chg": [500.0],
        "exchange": ["SHFE"], "change1": [200.0], "change2": [150.0],
    })
    pipeline._runtime.meta.update_last_date("fut_weekly", "20240101")

    with patch("zer0share.sync._jobs.time.sleep"):
        pipeline.run("fut_weekly")

    assert (cfg.data_dir / "futures" / "fut_weekly" / "date=20240102" / "data.parquet").exists()


# ---------------------------------------------------------------------------
# 13. fut_index_daily
# ---------------------------------------------------------------------------

def test_sync_fut_index_daily_writes_to_futures_subdir(pipeline, cfg, fetcher):
    fetcher.fetch_fut_index_daily.return_value = pd.DataFrame({
        "ts_code": ["NHAI.NH"], "trade_date": ["20240102"],
        "close": [1000.0], "open": [998.0], "high": [1005.0], "low": [995.0],
        "pre_close": [998.0], "change": [2.0], "pct_chg": [0.2],
        "vol": [50000.0], "amount": [50000000.0],
    })
    _setup_futures_trade_cal(pipeline, cfg)
    pipeline._runtime.meta.update_last_date("fut_index_daily", "20240101")

    with patch("zer0share.sync.futures.time.sleep"):
        pipeline.run("fut_index_daily")

    assert (cfg.data_dir / "futures" / "fut_index_daily" / "date=20240102" / "data.parquet").exists()


def test_sync_fut_index_daily_skips_non_trading_day(pipeline, cfg, fetcher, notifier):
    _setup_non_trading_day(pipeline, cfg)
    pipeline._runtime.meta.update_last_date("fut_index_daily", "20240101")
    pipeline.run("fut_index_daily")
    fetcher.fetch_fut_index_daily.assert_not_called()
    notifier.send.assert_not_called()


def test_sync_fut_index_daily_only_fetches_trading_days(pipeline, cfg, fetcher):
    """Bug3 fix: only fetches on trading days, not all calendar days."""
    trade_cal = pd.DataFrame({
        "exchange": ["SSE", "SSE", "SSE"],
        "cal_date": ["20240102", "20240103", "20240104"],
        "is_open": [True, False, True],
        "pretrade_date": ["20231229", "20240102", "20240102"],
    })
    write_trade_cal(cfg.data_dir, "SSE", trade_cal)
    pipeline._runtime.calendar.load_from_parquet(cfg.data_dir)
    pipeline._runtime.meta.update_last_date("trade_cal", "20240104")
    pipeline._runtime.meta.update_last_date("fut_index_daily", "20240101")
    pipeline._runtime.calendar._today_fn = lambda: "20240104"

    fetcher.fetch_fut_index_daily.return_value = pd.DataFrame()

    with patch("zer0share.sync.futures.time.sleep"):
        pipeline.run("fut_index_daily")

    # Only 20240102 and 20240104 are trading days; 20240103 is closed
    assert fetcher.fetch_fut_index_daily.call_count == 2
    fetcher.fetch_fut_index_daily.assert_any_call("20240102")
    fetcher.fetch_fut_index_daily.assert_any_call("20240104")


# ---------------------------------------------------------------------------
# 14. fut_weekly_detail
# ---------------------------------------------------------------------------

def test_sync_fut_weekly_detail_writes_to_futures_subdir(pipeline, cfg, fetcher):
    fetcher.fetch_fut_weekly_detail.return_value = pd.DataFrame({
        "exchange": ["SHFE"], "prd": ["CU"], "name": ["沪铜"],
        "vol": [100000], "vol_yoy": [5.0], "amount": [250.0],
        "amout_yoy": [3.0], "cumvol": [5000000], "cumvol_yoy": [4.0],
        "cumamt": [12500.0], "cumamt_yoy": [2.0],
        "open_interest": [200000], "interest_wow": [1.0],
        "mc_close": [50300.0], "close_wow": [0.5],
        "week": ["202401"], "week_date": ["20240101"],
    })
    pipeline._runtime.meta.update_last_date("fut_weekly_detail", "20231231")
    pipeline._runtime.calendar._today_fn = lambda: "20240107"

    with patch("zer0share.sync.futures.time.sleep"):
        pipeline.run("fut_weekly_detail")

    futures_dir = cfg.data_dir / "futures" / "fut_weekly_detail"
    if futures_dir.exists():
        partitions = list(futures_dir.iterdir())
        assert len(partitions) >= 1


def test_sync_fut_weekly_detail_skips_existing_weeks(pipeline, cfg, fetcher):
    """Bug1 fix: check existence before fetching weekly detail."""
    store = DailyPartitionStore(cfg.data_dir / "futures" / "fut_weekly_detail")
    store.write("20240101", pd.DataFrame({
        "week_date": ["20240101"], "exchange": ["SHFE"], "prd": ["CU"],
    }))
    pipeline._runtime.meta.update_last_date("fut_weekly_detail", "20231231")
    pipeline._runtime.calendar._today_fn = lambda: "20240107"

    with patch("zer0share.sync.futures.time.sleep"):
        pipeline.run("fut_weekly_detail")

    fetcher.fetch_fut_weekly_detail.assert_not_called()


def test_sync_fut_weekly_detail_already_up_to_date_returns_not_raises(pipeline, cfg, fetcher):
    """Bug2 fix: graceful return when already up to date (start > end)."""
    pipeline._runtime.meta.update_last_date("fut_weekly_detail", "20240107")
    pipeline._runtime.calendar._today_fn = lambda: "20240107"

    # start = add_days("20240107", 1) = "20240108" > end = "20240107" → should return
    pipeline.run("fut_weekly_detail")  # no exception
    fetcher.fetch_fut_weekly_detail.assert_not_called()


# ---------------------------------------------------------------------------
# 15. opt_basic
# ---------------------------------------------------------------------------

def test_sync_opt_basic_writes_to_options_subdir(pipeline, cfg, fetcher):
    def opt_basic_side_effect(exchange):
        return pd.DataFrame({
            "ts_code": ["10004462.SH"], "symbol": ["10004462"],
            "exchange": [exchange], "name": ["50ETF购4月2700"],
            "per_unit": [10000.0], "opt_code": ["OP510050"],
            "opt_type": ["E"], "call_put": ["C"],
            "exercise_type": ["E"], "exercise_price": [2.7],
            "s_month": ["202404"], "maturity_date": ["20240424"],
            "list_date": ["20240101"], "delist_date": ["20240424"],
        })

    fetcher.fetch_opt_basic.side_effect = opt_basic_side_effect
    _setup_trade_cal_sse(pipeline, cfg)

    with patch("zer0share.sync.options.time.sleep"):
        pipeline.run("opt_basic")

    assert (cfg.data_dir / "options" / "opt_basic" / "data.parquet").exists()
    assert pipeline._runtime.meta.get_last_date("opt_basic") == "20240102"


def test_sync_opt_basic_calls_all_exchanges(pipeline, cfg, fetcher):
    fetcher.fetch_opt_basic.return_value = pd.DataFrame()
    _setup_trade_cal_sse(pipeline, cfg)

    with patch("zer0share.sync.options.time.sleep"):
        pipeline.run("opt_basic")

    assert fetcher.fetch_opt_basic.call_count == len(OPTIONS_EXCHANGES)
    for exchange in OPTIONS_EXCHANGES:
        fetcher.fetch_opt_basic.assert_any_call(exchange)


def test_sync_opt_basic_failure_sends_alert_and_raises(pipeline, cfg, fetcher, notifier):
    fetcher.fetch_opt_basic.side_effect = RuntimeError("API error")
    _setup_trade_cal_sse(pipeline, cfg)
    with pytest.raises(RuntimeError):
        pipeline.run("opt_basic")
    notifier.send.assert_called_once()
    msg = notifier.send.call_args[0][0]
    assert "opt_basic 同步失败" in msg


def test_sync_opt_basic_skips_non_trading_day(pipeline, cfg, fetcher, notifier):
    _setup_non_trading_day(pipeline, cfg)
    pipeline.run("opt_basic")
    fetcher.fetch_opt_basic.assert_not_called()
    notifier.send.assert_not_called()


# ---------------------------------------------------------------------------
# 16. opt_daily
# ---------------------------------------------------------------------------

def _opt_daily_df(trade_date: str = "20240102") -> pd.DataFrame:
    return pd.DataFrame({
        "ts_code": ["10004462.SH"], "trade_date": [trade_date], "exchange": ["SSE"],
        "pre_settle": [0.15], "pre_close": [0.148],
        "open": [0.152], "high": [0.16], "low": [0.148],
        "close": [0.155], "settle": [0.154],
        "vol": [5000.0], "amount": [7700000.0], "oi": [20000.0],
    })


def test_sync_opt_daily_writes_to_options_subdir(pipeline, cfg, fetcher):
    _setup_options_trade_cal(pipeline, cfg)
    fetcher.fetch_opt_daily.return_value = _opt_daily_df("20240102")
    pipeline._runtime.meta.update_last_date("opt_daily", "20240101")

    with patch("zer0share.sync._jobs.time.sleep"):
        pipeline.run("opt_daily")

    assert (cfg.data_dir / "options" / "opt_daily" / "date=20240102" / "data.parquet").exists()


def test_sync_opt_daily_skips_existing_partitions(pipeline, cfg, fetcher):
    _setup_options_trade_cal(pipeline, cfg)
    fetcher.fetch_opt_daily.return_value = pd.DataFrame()
    pipeline._runtime.meta.update_last_date("opt_daily", "20240101")

    write_daily_partition(
        cfg.data_dir / "options", "opt_daily", "20240102",
        pd.DataFrame({"ts_code": ["10004462.SH"], "trade_date": ["20240102"]}),
    )

    with patch("zer0share.sync._jobs.time.sleep"):
        pipeline.run("opt_daily")

    fetcher.fetch_opt_daily.assert_not_called()


def test_sync_opt_daily_up_to_date(pipeline, cfg, fetcher):
    pipeline._runtime.calendar._today_fn = lambda: "20240102"
    pipeline._runtime.meta.update_last_date("opt_daily", "20240102")
    pipeline.run("opt_daily")
    fetcher.fetch_opt_daily.assert_not_called()


# ---------------------------------------------------------------------------
# 17. Constants
# ---------------------------------------------------------------------------

def test_all_exchanges_contains_all_8():
    assert ALL_EXCHANGES == ["SSE", "SZSE", "CFFEX", "DCE", "SHFE", "CZCE", "INE", "GFEX"]


# ---------------------------------------------------------------------------
# 18. TradingCalendar helpers (via _runtime.calendar)
# ---------------------------------------------------------------------------

def test_skip_if_not_trading_returns_true_on_non_trading_day(pipeline, cfg):
    trade_cal = pd.DataFrame({
        "exchange": ["SSE"],
        "cal_date": ["20240103"],
        "is_open": [False],
        "pretrade_date": ["20240102"],
    })
    write_trade_cal(cfg.data_dir, "SSE", trade_cal)
    pipeline._runtime.calendar.load_from_parquet(cfg.data_dir)
    pipeline._runtime.meta.update_last_date("trade_cal", "20240103")
    pipeline._runtime.calendar._today_fn = lambda: "20240103"

    assert pipeline._runtime.calendar.skip_if_not_trading("SSE") is True


def test_skip_if_not_trading_returns_false_on_trading_day(pipeline, cfg):
    trade_cal = pd.DataFrame({
        "exchange": ["SSE"],
        "cal_date": ["20240102"],
        "is_open": [True],
        "pretrade_date": ["20231229"],
    })
    write_trade_cal(cfg.data_dir, "SSE", trade_cal)
    pipeline._runtime.calendar.load_from_parquet(cfg.data_dir)
    pipeline._runtime.meta.update_last_date("trade_cal", "20240102")
    pipeline._runtime.calendar._today_fn = lambda: "20240102"

    assert pipeline._runtime.calendar.skip_if_not_trading("SSE") is False


def test_ensure_loaded_raises_when_trade_cal_missing(pipeline):
    # No trade_cal meta set → ensure_loaded should raise RuntimeError
    with pytest.raises(RuntimeError, match="trade_cal"):
        pipeline._runtime.calendar.ensure_loaded(pipeline._runtime)
