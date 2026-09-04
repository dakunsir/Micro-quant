import pytest

from microshare.quality.targets import QUALITY_TARGETS, get_targets, select_targets


def test_quality_targets_cover_first_version_scope():
    assert set(QUALITY_TARGETS) == {
        "daily_kline",
        "adj_factor",
        "index_daily",
        "fund_daily",
        "fund_adj",
        "fut_daily",
        "opt_daily",
    }


def test_select_targets_by_market():
    targets = select_targets(market="etf")

    assert [target.table for target in targets] == ["fund_daily", "fund_adj"]


def test_select_targets_by_table():
    targets = select_targets(table="daily_kline")

    assert len(targets) == 1
    assert targets[0].market == "stock"
    assert targets[0].primary_key == ("ts_code", "trade_date")


def test_select_all_targets_keeps_registry_order():
    targets = select_targets(all_targets=True)

    assert [target.table for target in targets] == list(QUALITY_TARGETS)


def test_select_targets_rejects_unknown_table():
    with pytest.raises(ValueError, match="unknown quality table"):
        select_targets(table="daily_basic")


def test_get_targets_rejects_unknown_names():
    with pytest.raises(ValueError, match="unknown quality table"):
        get_targets(["missing"])
