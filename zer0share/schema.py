BASIC_COLS = [
    "ts_code",
    "symbol",
    "name",
    "area",
    "industry",
    "fullname",
    "enname",
    "cnspell",
    "market",
    "exchange",
    "curr_type",
    "list_status",
    "list_date",
    "delist_date",
    "is_hs",
    "act_name",
    "act_ent_type",
]
DAILY_COLS = [
    "ts_code", "trade_date", "open", "high", "low",
    "close", "pre_close", "change", "pct_chg", "vol", "amount"
]
TRADE_CAL_COLS = ["exchange", "cal_date", "is_open", "pretrade_date"]
ADJ_FACTOR_COLS = ["ts_code", "trade_date", "adj_factor"]
DAILY_BASIC_COLS = [
    "ts_code",
    "trade_date",
    "close",
    "turnover_rate",
    "turnover_rate_f",
    "volume_ratio",
    "pe",
    "pe_ttm",
    "pb",
    "ps",
    "ps_ttm",
    "dv_ratio",
    "dv_ttm",
    "total_share",
    "float_share",
    "free_share",
    "total_mv",
    "circ_mv",
    "limit_status",
]
STOCK_ST_COLS = ["ts_code", "name", "trade_date", "type", "type_name"]
SUSPEND_D_COLS = ["ts_code", "trade_date", "suspend_timing", "suspend_type"]
STK_LIMIT_COLS = ["trade_date", "ts_code", "pre_close", "up_limit", "down_limit"]
INDEX_WEIGHT_COLS = ["index_code", "con_code", "trade_date", "weight"]
INDEX_DAILY_COLS = [
    "ts_code", "trade_date", "open", "high", "low",
    "close", "pre_close", "change", "pct_chg", "vol", "amount",
]
ETF_BASIC_COLS = [
    "ts_code",
    "csname",
    "extname",
    "cname",
    "index_code",
    "index_name",
    "setup_date",
    "list_date",
    "list_status",
    "exchange",
    "mgr_name",
    "custod_name",
    "mgt_fee",
    "etf_type",
]
ETF_INDEX_COLS = [
    "ts_code",
    "indx_name",
    "indx_csname",
    "pub_party_name",
    "pub_date",
    "base_date",
    "bp",
    "adj_circle",
]
FUND_DAILY_COLS = [
    "ts_code", "trade_date", "open", "high", "low",
    "close", "pre_close", "change", "pct_chg", "vol", "amount"
]
FUND_ADJ_COLS = ["ts_code", "trade_date", "adj_factor", "discount_rate"]
SW_CLASSIFY_COLS = [
    "index_code", "industry_name", "level", "parent_code",
    "industry_code", "is_pub", "src",
]
SW_MEMBER_COLS = [
    "l1_code", "l1_name", "l2_code", "l2_name",
    "l3_code", "l3_name", "ts_code", "name",
    "in_date", "out_date", "is_new",
]
CI_MEMBER_COLS = [
    "l1_code", "l1_name", "l2_code", "l2_name",
    "l3_code", "l3_name", "ts_code", "name",
    "in_date", "out_date", "is_new",
]
OPT_BASIC_COLS = [
    "ts_code", "symbol", "exchange", "name", "per_unit",
    "opt_code", "opt_type", "call_put", "exercise_type",
    "exercise_price", "s_month", "maturity_date",
    "list_price", "list_date", "delist_date",
    "last_edate", "last_ddate", "quote_unit", "min_price_chg",
]
OPT_DAILY_COLS = [
    "ts_code", "trade_date", "exchange",
    "pre_settle", "pre_close",
    "open", "high", "low", "close", "settle",
    "vol", "amount", "oi",
]
FUT_BASIC_COLS = [
    "ts_code", "symbol", "exchange", "name", "fut_code",
    "multiplier", "trade_unit", "per_unit", "quote_unit",
    "quote_unit_desc", "d_mode_desc", "list_date", "delist_date",
    "d_month", "last_ddate", "trade_time_desc",
]
FUT_DAILY_COLS = [
    "ts_code", "trade_date", "pre_close", "pre_settle",
    "open", "high", "low", "close", "settle",
    "change1", "change2", "vol", "amount", "oi", "oi_chg",
    "delv_settle",
]
FUT_HOLDING_COLS = [
    "trade_date", "symbol", "broker", "vol", "vol_chg",
    "long_hld", "long_chg", "short_hld", "short_chg", "exchange",
]
FUT_WSR_COLS = [
    "trade_date", "symbol", "fut_name", "warehouse", "wh_id",
    "pre_vol", "vol", "vol_chg", "area", "year", "grade",
    "brand", "place", "pd", "is_ct", "unit", "exchange",
]
FUT_SETTLE_COLS = [
    "ts_code", "trade_date", "settle", "trading_fee_rate",
    "trading_fee", "delivery_fee", "b_hedging_margin_rate",
    "s_hedging_margin_rate", "long_margin_rate", "short_margin_rate",
    "offset_today_fee", "exchange",
]
FUT_MAPPING_COLS = [
    "ts_code", "trade_date", "mapping_ts_code",
]
FT_LIMIT_COLS = [
    "trade_date", "ts_code", "name", "up_limit", "down_limit",
    "m_ratio", "cont", "exchange",
]
FUT_WEEKLY_COLS = [
    "ts_code", "trade_date", "freq", "open", "high", "low",
    "close", "pre_close", "settle", "pre_settle", "vol",
    "amount", "oi", "oi_chg", "exchange", "change1", "change2",
]
FUT_MONTHLY_COLS = FUT_WEEKLY_COLS
FUT_INDEX_DAILY_COLS = [
    "ts_code", "trade_date", "close", "open", "high", "low",
    "pre_close", "change", "pct_chg", "vol", "amount",
]
FUT_WEEKLY_DETAIL_COLS = [
    "exchange", "prd", "name", "vol", "vol_yoy", "amount",
    "amout_yoy", "cumvol", "cumvol_yoy", "cumamt", "cumamt_yoy",
    "open_interest", "interest_wow", "mc_close", "close_wow",
    "week", "week_date",
]
