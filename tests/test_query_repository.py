import pandas as pd
import pytest

from zer0share.query import QueryContext
from zer0share.query.repository import (
    BaseParquetRepository,
    DailyPartitionRepository,
    DailyTableSpec,
    ParquetQueryEngine,
    TableSpec,
    eq_filter,
    in_filter,
)


def test_eq_filter_rejects_unknown_column():
    with pytest.raises(ValueError, match="unknown filter column: not_a_column"):
        eq_filter("not_a_column", "x", ["ts_code"])


def test_in_filter_builds_bound_placeholders():
    filt = in_filter("ts_code", ["000001.SZ", "000002.SZ"], ["ts_code"])

    assert filt.clause == "ts_code IN (?, ?)"
    assert filt.params == ("000001.SZ", "000002.SZ")


def test_engine_rejects_invalid_order_by(tmp_path):
    path = tmp_path / "data.parquet"
    pd.DataFrame({"ts_code": ["000001.SZ"]}).to_parquet(path)

    engine = ParquetQueryEngine()

    with pytest.raises(ValueError, match="invalid order_by"):
        engine.select(
            source=path,
            columns=["ts_code"],
            filters=[],
            order_by="ts_code; DROP TABLE x",
        )


def test_base_repository_queries_static_parquet(tmp_path):
    (tmp_path / "basic").mkdir()
    pd.DataFrame(
        {
            "ts_code": ["000002.SZ", "000001.SZ"],
            "name": ["B", "A"],
        }
    ).to_parquet(tmp_path / "basic" / "data.parquet")

    repo = BaseParquetRepository(
        QueryContext(tmp_path),
        TableSpec(
            name="basic",
            path_parts=("basic",),
            columns=["ts_code", "name"],
            parquet_pattern="data.parquet",
            sync_table="basic",
            order_by="ts_code",
        ),
        ParquetQueryEngine(),
    )

    result = repo.query(
        fields="ts_code",
        filters=[eq_filter("name", "A", ["ts_code", "name"])],
    )

    assert result.to_dict("records") == [{"ts_code": "000001.SZ"}]


def test_daily_partition_repository_rejects_trade_date_with_range(tmp_path):
    (tmp_path / "daily_kline").mkdir()
    repo = DailyPartitionRepository(
        QueryContext(tmp_path),
        DailyTableSpec(
            name="daily_kline",
            path_parts=("daily_kline",),
            columns=["ts_code", "trade_date"],
            parquet_pattern="date=*/data.parquet",
            sync_table="daily_kline",
            order_by="ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
        ParquetQueryEngine(),
    )

    with pytest.raises(ValueError, match="trade_date cannot be combined"):
        repo.query(trade_date="20240102", start_date="20240101")


def test_daily_partition_repository_queries_by_date_range(tmp_path):
    day1 = tmp_path / "daily_kline" / "date=20240101"
    day2 = tmp_path / "daily_kline" / "date=20240102"
    day1.mkdir(parents=True)
    day2.mkdir(parents=True)
    pd.DataFrame(
        {"ts_code": ["000001.SZ"], "trade_date": ["20240101"], "close": [10.0]}
    ).to_parquet(day1 / "data.parquet")
    pd.DataFrame(
        {"ts_code": ["000002.SZ"], "trade_date": ["20240102"], "close": [20.0]}
    ).to_parquet(day2 / "data.parquet")

    repo = DailyPartitionRepository(
        QueryContext(tmp_path),
        DailyTableSpec(
            name="daily_kline",
            path_parts=("daily_kline",),
            columns=["ts_code", "trade_date", "close"],
            parquet_pattern="date=*/data.parquet",
            sync_table="daily_kline",
            order_by="ts_code, trade_date",
            hive_partitioning=True,
            union_by_name=True,
        ),
        ParquetQueryEngine(),
    )

    result = repo.query(
        start_date="20240102",
        end_date="20240102",
        fields="ts_code,close",
    )

    assert result.to_dict("records") == [{"ts_code": "000002.SZ", "close": 20.0}]


def test_daily_partition_repository_supports_table_without_code_column(tmp_path):
    day = tmp_path / "futures" / "fut_holding" / "date=20240102"
    day.mkdir(parents=True)
    pd.DataFrame(
        {
            "trade_date": ["20240102"],
            "symbol": ["CU"],
            "broker": ["broker-a"],
        }
    ).to_parquet(day / "data.parquet")

    repo = DailyPartitionRepository(
        QueryContext(tmp_path),
        DailyTableSpec(
            name="fut_holding",
            path_parts=("futures", "fut_holding"),
            columns=["trade_date", "symbol", "broker"],
            parquet_pattern="date=*/data.parquet",
            sync_table="fut_holding",
            order_by="trade_date, symbol, broker",
            hive_partitioning=True,
            union_by_name=True,
            code_column=None,
        ),
        ParquetQueryEngine(),
    )

    result = repo.query(
        trade_date="20240102",
        filters=[eq_filter("symbol", "CU", ["trade_date", "symbol", "broker"])],
    )

    assert result.to_dict("records") == [
        {"trade_date": "20240102", "symbol": "CU", "broker": "broker-a"}
    ]
