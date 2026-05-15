from datetime import date, timedelta

import pandas as pd

from zer0share.storage import write_basic, write_daily_partition, write_daily_kline, write_index_weight
from zer0share.universe import build_universe_detail, build_universes


def _basic(codes: list[str], trade_date: date) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts_code": codes,
            "symbol": [code.split(".")[0] for code in codes],
            "name": [f"Stock{i:02d}" for i in range(len(codes))],
            "area": ["深圳"] * len(codes),
            "industry": ["行业"] * len(codes),
            "fullname": [f"Stock {i:02d}" for i in range(len(codes))],
            "enname": [f"Stock {i:02d}" for i in range(len(codes))],
            "cnspell": ["stock"] * len(codes),
            "market": ["主板"] * len(codes),
            "exchange": ["SZSE"] * len(codes),
            "curr_type": ["CNY"] * len(codes),
            "list_status": ["L"] * len(codes),
            "list_date": [trade_date - timedelta(days=365)] * len(codes),
            "delist_date": [None] * len(codes),
            "is_hs": ["N"] * len(codes),
            "act_name": [""] * len(codes),
            "act_ent_type": [""] * len(codes),
        }
    )


def _daily(codes: list[str], trade_date: date, amount: float = 20000.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts_code": codes,
            "trade_date": [trade_date] * len(codes),
            "open": [10.0] * len(codes),
            "high": [11.0] * len(codes),
            "low": [9.0] * len(codes),
            "close": [10.5] * len(codes),
            "pre_close": [10.0] * len(codes),
            "change": [0.5] * len(codes),
            "pct_chg": [5.0] * len(codes),
            "vol": [1000.0] * len(codes),
            "amount": [amount] * len(codes),
        }
    )


def test_build_universe_detail_applies_core_filters(tmp_path):
    trade_date = date(2024, 1, 30)
    codes = [f"{i:06d}.SZ" for i in range(1, 21)]
    write_basic(tmp_path, _basic(codes, trade_date))

    for offset in range(20):
        day = trade_date - timedelta(days=19 - offset)
        df = _daily(codes, day)
        df.loc[df["ts_code"] == "000005.SZ", "amount"] = 1000.0
        if day == trade_date:
            df.loc[df["ts_code"] == "000004.SZ", ["open", "high", "low", "close"]] = 12.0
            df.loc[df["ts_code"] == "000007.SZ", ["open", "high", "low", "close"]] = 8.0
        write_daily_kline(tmp_path, day, df)

    daily_basic = pd.DataFrame(
        {
            "ts_code": codes,
            "trade_date": [trade_date] * len(codes),
            "close": [10.5] * len(codes),
            "turnover_rate": [1.0] * len(codes),
            "turnover_rate_f": [1.0] * len(codes),
            "volume_ratio": [1.0] * len(codes),
            "pe": [10.0] * len(codes),
            "pe_ttm": [10.0] * len(codes),
            "pb": [1.0] * len(codes),
            "ps": [1.0] * len(codes),
            "ps_ttm": [1.0] * len(codes),
            "dv_ratio": [0.0] * len(codes),
            "dv_ttm": [0.0] * len(codes),
            "total_share": [1000.0] * len(codes),
            "float_share": [1000.0] * len(codes),
            "free_share": [1000.0] * len(codes),
            "total_mv": list(range(20, 0, -1)),
            "circ_mv": list(range(20, 0, -1)),
        }
    )
    write_daily_partition(tmp_path, "daily_basic", trade_date, daily_basic)
    write_daily_partition(
        tmp_path,
        "stock_st",
        trade_date,
        pd.DataFrame(
            {
                "ts_code": ["000002.SZ"],
                "name": ["ST示例"],
                "trade_date": [trade_date],
                "type": ["ST"],
                "type_name": ["风险警示板"],
            }
        ),
    )
    write_daily_partition(
        tmp_path,
        "suspend_d",
        trade_date,
        pd.DataFrame(
            {
                "ts_code": ["000003.SZ"],
                "trade_date": [trade_date],
                "suspend_timing": [None],
                "suspend_type": ["S"],
            }
        ),
    )
    write_daily_partition(
        tmp_path,
        "stk_limit",
        trade_date,
        pd.DataFrame(
            {
                "trade_date": [trade_date] * len(codes),
                "ts_code": codes,
                "pre_close": [10.0] * len(codes),
                "up_limit": [12.0] * len(codes),
                "down_limit": [8.0] * len(codes),
            }
        ),
    )

    detail = build_universe_detail(tmp_path, trade_date).set_index("ts_code")

    assert detail.loc["000001.SZ", "in_trade_base"] == True
    assert detail.loc["000002.SZ", "in_research_base"] == False
    assert detail.loc["000003.SZ", "in_research_base"] == True
    assert detail.loc["000003.SZ", "in_trade_base"] == False
    assert detail.loc["000004.SZ", "in_trade_base"] == False
    assert detail.loc["000005.SZ", "in_research_base"] == False
    assert detail.loc["000007.SZ", "in_trade_base"] == False


def test_build_universes_writes_index_intersections(tmp_path):
    trade_date = date(2024, 1, 30)
    codes = [f"{i:06d}.SZ" for i in range(1, 21)]
    write_basic(tmp_path, _basic(codes, trade_date))
    for offset in range(20):
        day = trade_date - timedelta(days=19 - offset)
        write_daily_kline(tmp_path, day, _daily(codes, day))

    daily_basic = pd.DataFrame(
        {
            "ts_code": codes,
            "trade_date": [trade_date] * len(codes),
            "close": [10.5] * len(codes),
            "turnover_rate": [1.0] * len(codes),
            "turnover_rate_f": [1.0] * len(codes),
            "volume_ratio": [1.0] * len(codes),
            "pe": [10.0] * len(codes),
            "pe_ttm": [10.0] * len(codes),
            "pb": [1.0] * len(codes),
            "ps": [1.0] * len(codes),
            "ps_ttm": [1.0] * len(codes),
            "dv_ratio": [0.0] * len(codes),
            "dv_ttm": [0.0] * len(codes),
            "total_share": [1000.0] * len(codes),
            "float_share": [1000.0] * len(codes),
            "free_share": [1000.0] * len(codes),
            "total_mv": list(range(1, 21)),
            "circ_mv": list(range(1, 21)),
        }
    )
    write_daily_partition(tmp_path, "daily_basic", trade_date, daily_basic)
    write_daily_partition(tmp_path, "stock_st", trade_date, pd.DataFrame(columns=["ts_code", "name", "trade_date", "type", "type_name"]))
    write_daily_partition(tmp_path, "suspend_d", trade_date, pd.DataFrame(columns=["ts_code", "trade_date", "suspend_timing", "suspend_type"]))
    write_daily_partition(
        tmp_path,
        "stk_limit",
        trade_date,
        pd.DataFrame(
            {
                "trade_date": [trade_date] * len(codes),
                "ts_code": codes,
                "pre_close": [10.0] * len(codes),
                "up_limit": [12.0] * len(codes),
                "down_limit": [8.0] * len(codes),
            }
        ),
    )
    for index_code in ["399300.SZ", "000905.SH", "000852.SH"]:
        write_index_weight(
            tmp_path,
            index_code,
            trade_date,
            pd.DataFrame(
                {
                    "index_code": [index_code, index_code],
                    "con_code": ["000001.SZ", "000002.SZ"],
                    "trade_date": [trade_date, trade_date],
                    "weight": [50.0, 50.0],
                }
            ),
        )

    counts = build_universes(tmp_path, trade_date)

    assert counts["univ_trade_hs300"] == 1
    hs300 = pd.read_parquet(
        tmp_path / "universe" / "name=univ_trade_hs300" / "date=20240130" / "data.parquet"
    )
    assert hs300["ts_code"].tolist() == ["000002.SZ"]
