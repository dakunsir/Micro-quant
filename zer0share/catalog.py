"""
catalog.py — central registry of all TableSpec / DailyTableSpec constants.

Both the query layer (zer0share/query/*.py) and the sync layer
(zer0share/sync/*.py) import specs from here so the two layers always
stay in sync with each other.  This module contains no logic — only
named constants.
"""

from zer0share.query.repository import DailyTableSpec, TableSpec
from zer0share.schema import (
    ADJ_FACTOR_COLS,
    BASIC_COLS,
    CI_MEMBER_COLS,
    DAILY_BASIC_COLS,
    DAILY_COLS,
    FT_LIMIT_COLS,
    FUT_BASIC_COLS,
    FUT_DAILY_COLS,
    FUT_HOLDING_COLS,
    FUT_INDEX_DAILY_COLS,
    FUT_MAPPING_COLS,
    FUT_MONTHLY_COLS,
    FUT_SETTLE_COLS,
    FUT_WEEKLY_COLS,
    FUT_WEEKLY_DETAIL_COLS,
    FUT_WSR_COLS,
    INDEX_DAILY_COLS,
    INDEX_WEIGHT_COLS,
    OPT_BASIC_COLS,
    OPT_DAILY_COLS,
    STOCK_ST_COLS,
    STK_LIMIT_COLS,
    SUSPEND_D_COLS,
    SW_CLASSIFY_COLS,
    SW_MEMBER_COLS,
    TRADE_CAL_COLS,
)

# ---------------------------------------------------------------------------
# Equities + calendar
# ---------------------------------------------------------------------------

BASIC_SPEC = TableSpec(
    name="basic",
    path_parts=("basic",),
    columns=BASIC_COLS,
    parquet_pattern="data.parquet",
    sync_table="basic",
    order_by="ts_code",
)

DAILY_KLINE_SPEC = DailyTableSpec(
    name="daily_kline",
    path_parts=("daily_kline",),
    columns=DAILY_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="daily_kline",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
)

ADJ_FACTOR_SPEC = DailyTableSpec(
    name="adj_factor",
    path_parts=("adj_factor",),
    columns=ADJ_FACTOR_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="adj_factor",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
)

DAILY_BASIC_SPEC = DailyTableSpec(
    name="daily_basic",
    path_parts=("daily_basic",),
    columns=DAILY_BASIC_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="daily_basic",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
)

STOCK_ST_SPEC = DailyTableSpec(
    name="stock_st",
    path_parts=("stock_st",),
    columns=STOCK_ST_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="stock_st",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
)

SUSPEND_D_SPEC = DailyTableSpec(
    name="suspend_d",
    path_parts=("suspend_d",),
    columns=SUSPEND_D_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="suspend_d",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
)

STK_LIMIT_SPEC = DailyTableSpec(
    name="stk_limit",
    path_parts=("stk_limit",),
    columns=STK_LIMIT_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="stk_limit",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
)

INDEX_DAILY_SPEC = DailyTableSpec(
    name="index_daily",
    path_parts=("index_daily",),
    columns=INDEX_DAILY_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="index_daily",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
)

INDEX_WEIGHT_SPEC = TableSpec(
    name="index_weight",
    path_parts=("index_weight",),
    columns=INDEX_WEIGHT_COLS,
    parquet_pattern="index_code=*/date=*/data.parquet",
    sync_table="index_weight",
    order_by="index_code, con_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
)

TRADE_CAL_SPEC = TableSpec(
    name="trade_cal",
    path_parts=("trade_cal",),
    columns=TRADE_CAL_COLS,
    parquet_pattern="exchange=*/data.parquet",
    sync_table="trade_cal",
    order_by="exchange, cal_date",
    hive_partitioning=True,
)

# ---------------------------------------------------------------------------
# Industry
# ---------------------------------------------------------------------------

SW_CLASSIFY_SPEC = TableSpec(
    name="sw_classify",
    path_parts=("industry", "sw_classify"),
    columns=SW_CLASSIFY_COLS,
    parquet_pattern="data.parquet",
    sync_table="industry",
    order_by="industry_code",
)

SW_MEMBER_SPEC = TableSpec(
    name="sw_member",
    path_parts=("industry", "sw_member"),
    columns=SW_MEMBER_COLS,
    parquet_pattern="data.parquet",
    sync_table="industry",
    order_by="ts_code, l1_code",
)

CI_MEMBER_SPEC = TableSpec(
    name="ci_member",
    path_parts=("industry", "ci_member"),
    columns=CI_MEMBER_COLS,
    parquet_pattern="data.parquet",
    sync_table="ci_member",
    order_by="ts_code, l1_code",
)

# ---------------------------------------------------------------------------
# Futures
# ---------------------------------------------------------------------------

FUT_BASIC_SPEC = TableSpec(
    name="fut_basic",
    path_parts=("futures", "fut_basic"),
    columns=FUT_BASIC_COLS,
    parquet_pattern="data.parquet",
    sync_table="fut_basic",
    order_by="ts_code",
)

FUT_DAILY_SPEC = DailyTableSpec(
    name="fut_daily",
    path_parts=("futures", "fut_daily"),
    columns=FUT_DAILY_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="fut_daily",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
    first_date="19960101",
)

FUT_HOLDING_SPEC = DailyTableSpec(
    name="fut_holding",
    path_parts=("futures", "fut_holding"),
    columns=FUT_HOLDING_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="fut_holding",
    order_by="trade_date, symbol, broker",
    hive_partitioning=True,
    union_by_name=True,
    code_column=None,
    first_date="20020101",
)

FUT_WSR_SPEC = DailyTableSpec(
    name="fut_wsr",
    path_parts=("futures", "fut_wsr"),
    columns=FUT_WSR_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="fut_wsr",
    order_by="trade_date, symbol, warehouse",
    hive_partitioning=True,
    union_by_name=True,
    code_column=None,
    first_date="20060101",
)

FUT_SETTLE_SPEC = DailyTableSpec(
    name="fut_settle",
    path_parts=("futures", "fut_settle"),
    columns=FUT_SETTLE_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="fut_settle",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
    first_date="20120101",
)

FUT_MAPPING_SPEC = DailyTableSpec(
    name="fut_mapping",
    path_parts=("futures", "fut_mapping"),
    columns=FUT_MAPPING_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="fut_mapping",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
)

FT_LIMIT_SPEC = DailyTableSpec(
    name="ft_limit",
    path_parts=("futures", "ft_limit"),
    columns=FT_LIMIT_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="ft_limit",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
)

FUT_WEEKLY_SPEC = DailyTableSpec(
    name="fut_weekly",
    path_parts=("futures", "fut_weekly"),
    columns=FUT_WEEKLY_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="fut_weekly",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
)

FUT_MONTHLY_SPEC = DailyTableSpec(
    name="fut_monthly",
    path_parts=("futures", "fut_monthly"),
    columns=FUT_MONTHLY_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="fut_monthly",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
)

FUT_INDEX_DAILY_SPEC = DailyTableSpec(
    name="fut_index_daily",
    path_parts=("futures", "fut_index_daily"),
    columns=FUT_INDEX_DAILY_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="fut_index_daily",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
)

FUT_WEEKLY_DETAIL_SPEC = DailyTableSpec(
    name="fut_weekly_detail",
    path_parts=("futures", "fut_weekly_detail"),
    columns=FUT_WEEKLY_DETAIL_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="fut_weekly_detail",
    order_by="week_date, exchange, prd",
    hive_partitioning=True,
    union_by_name=True,
    date_column="week_date",
    code_column=None,
)

# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------

OPT_BASIC_SPEC = TableSpec(
    name="opt_basic",
    path_parts=("options", "opt_basic"),
    columns=OPT_BASIC_COLS,
    parquet_pattern="data.parquet",
    sync_table="opt_basic",
    order_by="ts_code",
)

OPT_DAILY_SPEC = DailyTableSpec(
    name="opt_daily",
    path_parts=("options", "opt_daily"),
    columns=OPT_DAILY_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="opt_daily",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
    first_date="20150209",
)
