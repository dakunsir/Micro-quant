"""
catalog.py — central registry of all TableSpec / DailyTableSpec constants.

Both the query layer (microshare/query/*.py) and the sync layer
(microshare/sync/*.py) import specs from here so the two layers always
stay in sync with each other.  This module contains no logic — only
named constants.
"""

from microshare.query.repository import DailyTableSpec, TableSpec
from microshare.schema import (
    ADJ_FACTOR_COLS,
    BASIC_COLS,
    CI_MEMBER_COLS,
    DAILY_BASIC_COLS,
    DAILY_COLS,
    ETF_BASIC_COLS,
    ETF_INDEX_COLS,
    ETF_SHARE_SIZE_COLS,
    ETF_SH_CONS_COLS,
    FUND_ADJ_COLS,
    FUND_DAILY_COLS,
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
    IDX_ANNS_COLS,
    INDEX_WEIGHT_COLS,
    OPT_BASIC_COLS,
    OPT_DAILY_COLS,
    RICEQUANT_ETF_BASIC_COLS,
    RICEQUANT_ETF_MINUTE_COLS,
    STOCK_ST_COLS,
    STK_LIMIT_COLS,
    SUSPEND_D_COLS,
    SW_CLASSIFY_COLS,
    SW_DAILY_COLS,
    SW_MEMBER_COLS,
    TRADE_CAL_COLS,
)

# ---------------------------------------------------------------------------
# Equities + calendar
# ---------------------------------------------------------------------------

BASIC_SPEC = TableSpec(
    name="basic",
    path_parts=("stock", "basic"),
    columns=BASIC_COLS,
    parquet_pattern="data.parquet",
    sync_table="basic",
    order_by="ts_code",
)

DAILY_KLINE_SPEC = DailyTableSpec(
    name="daily_kline",
    path_parts=("stock", "daily_kline"),
    columns=DAILY_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="daily_kline",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
    first_date="19901219",
)

ADJ_FACTOR_SPEC = DailyTableSpec(
    name="adj_factor",
    path_parts=("stock", "adj_factor"),
    columns=ADJ_FACTOR_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="adj_factor",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
    first_date="19901219",
)

DAILY_BASIC_SPEC = DailyTableSpec(
    name="daily_basic",
    path_parts=("stock", "daily_basic"),
    columns=DAILY_BASIC_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="daily_basic",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
    first_date="19901219",
)

STOCK_ST_SPEC = DailyTableSpec(
    name="stock_st",
    path_parts=("stock", "stock_st"),
    columns=STOCK_ST_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="stock_st",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
)

SUSPEND_D_SPEC = DailyTableSpec(
    name="suspend_d",
    path_parts=("stock", "suspend_d"),
    columns=SUSPEND_D_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="suspend_d",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
    first_date="20000104",
)

STK_LIMIT_SPEC = DailyTableSpec(
    name="stk_limit",
    path_parts=("stock", "stk_limit"),
    columns=STK_LIMIT_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="stk_limit",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
    first_date="20070104",
)

INDEX_DAILY_SPEC = DailyTableSpec(
    name="index_daily",
    path_parts=("index", "index_daily"),
    columns=INDEX_DAILY_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="index_daily",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
    first_date="19901219",
)

INDEX_WEIGHT_SPEC = TableSpec(
    name="index_weight",
    path_parts=("index", "index_weight"),
    columns=INDEX_WEIGHT_COLS,
    parquet_pattern="index_code=*/date=*/data.parquet",
    sync_table="index_weight",
    order_by="index_code, con_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
)

IDX_ANNS_SPEC = DailyTableSpec(
    name="idx_anns",
    path_parts=("index", "idx_anns"),
    columns=IDX_ANNS_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="idx_anns",
    order_by="ann_date DESC, source, title",
    hive_partitioning=True,
    union_by_name=True,
    first_date="20040101",
    date_column="ann_date",
    code_column=None,
)

# ---------------------------------------------------------------------------
# ETF
# ---------------------------------------------------------------------------

ETF_BASIC_SPEC = TableSpec(
    name="etf_basic",
    path_parts=("etf", "etf_basic"),
    columns=ETF_BASIC_COLS,
    parquet_pattern="data.parquet",
    sync_table="etf_basic",
    order_by="ts_code",
)

ETF_INDEX_SPEC = TableSpec(
    name="etf_index",
    path_parts=("etf", "etf_index"),
    columns=ETF_INDEX_COLS,
    parquet_pattern="data.parquet",
    sync_table="etf_index",
    order_by="ts_code",
)

FUND_DAILY_SPEC = DailyTableSpec(
    name="fund_daily",
    path_parts=("etf", "fund_daily"),
    columns=FUND_DAILY_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="fund_daily",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
    first_date="20050223",
)

FUND_ADJ_SPEC = DailyTableSpec(
    name="fund_adj",
    path_parts=("etf", "fund_adj"),
    columns=FUND_ADJ_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="fund_adj",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
    first_date="20100101",
)

ETF_SHARE_SIZE_SPEC = DailyTableSpec(
    name="etf_share_size",
    path_parts=("etf", "etf_share_size"),
    columns=ETF_SHARE_SIZE_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="etf_share_size",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
    first_date="20100101",
)

ETF_SH_CONS_SPEC = DailyTableSpec(
    name="etf_sh_cons",
    path_parts=("etf", "etf_sh_cons"),
    columns=ETF_SH_CONS_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="etf_sh_cons",
    order_by="ts_code, trade_date, con_code",
    hive_partitioning=True,
    union_by_name=True,
    first_date="20100101",
)

# ---------------------------------------------------------------------------
# RiceQuant
# ---------------------------------------------------------------------------

RICEQUANT_ETF_BASIC_SPEC = TableSpec(
    name="ricequant_etf_basic",
    path_parts=("ricequant", "etf_basic"),
    columns=RICEQUANT_ETF_BASIC_COLS,
    parquet_pattern="data.parquet",
    sync_table="ricequant_etf_basic",
    order_by="order_book_id",
)

RICEQUANT_ETF_MINUTE_SPEC = DailyTableSpec(
    name="ricequant_etf_minute",
    path_parts=("ricequant", "etf_minute"),
    columns=RICEQUANT_ETF_MINUTE_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="ricequant_etf_minute",
    order_by="order_book_id, datetime",
    hive_partitioning=True,
    union_by_name=True,
)

# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

TRADE_CAL_SPEC = TableSpec(
    name="trade_cal",
    path_parts=("stock", "trade_cal"),
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
    path_parts=("stock", "industry", "sw_classify"),
    columns=SW_CLASSIFY_COLS,
    parquet_pattern="data.parquet",
    sync_table="industry",
    order_by="industry_code",
)

SW_MEMBER_SPEC = TableSpec(
    name="sw_member",
    path_parts=("stock", "industry", "sw_member"),
    columns=SW_MEMBER_COLS,
    parquet_pattern="data.parquet",
    sync_table="industry",
    order_by="ts_code, l1_code",
)

SW_DAILY_SPEC = DailyTableSpec(
    name="sw_daily",
    path_parts=("stock", "industry", "sw_daily"),
    columns=SW_DAILY_COLS,
    parquet_pattern="date=*/data.parquet",
    sync_table="sw_daily",
    order_by="ts_code, trade_date",
    hive_partitioning=True,
    union_by_name=True,
    first_date="20000104",
)

CI_MEMBER_SPEC = TableSpec(
    name="ci_member",
    path_parts=("stock", "industry", "ci_member"),
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
    first_date="19950417",
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
    first_date="20070101",
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
    first_date="19950417",
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
    first_date="20050101",
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
    first_date="19950417",
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
    first_date="19950417",
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
    first_date="20060101",
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
    first_date="20151201",
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
