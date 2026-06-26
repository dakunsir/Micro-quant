# zer0share Local Query API

This reference lists the local Tushare-like interfaces exposed by `zer0share.pro_api()`.

All date strings use `YYYYMMDD`. Common optional parameters are `fields`, `limit`, and `offset` unless noted.

## Entry Points

```python
from zer0share import pro_api

pro = pro_api()
df = pro.daily(ts_code="000001.SZ", start_date="20240101", end_date="20240131")
df = pro.query("daily", ts_code="000001.SZ", start_date="20240101", end_date="20240131")
```

`pro_api(config_path="config/settings.toml")` loads `data_dir` from the zer0share config.

## Calendar

- `trade_cal(exchange="SSE", start_date=None, end_date=None, is_open=None, fields=None, limit=None, offset=None)`
  - Local sync table: `trade_cal`
  - Query calendar dates, open flags, and previous trading days.

## Equities

- `stock_basic(ts_code=None, name=None, market=None, list_status="L", exchange=None, is_hs=None, fields=None, limit=None, offset=None)`
  - Local sync table: `basic`
  - Stock metadata and listing status.

- `daily(ts_code=None, trade_date=None, start_date=None, end_date=None, fields=None, limit=None, offset=None)`
  - Local sync table: `daily_kline`
  - Daily OHLCV bars.

- `adj_factor(ts_code=None, trade_date=None, start_date=None, end_date=None, fields=None, limit=None, offset=None)`
  - Local sync table: `adj_factor`
  - Adjustment factors for split/dividend adjusted prices.

- `daily_basic(ts_code=None, trade_date=None, start_date=None, end_date=None, fields=None, limit=None, offset=None)`
  - Local sync table: `daily_basic`
  - Daily valuation and fundamental indicators.

- `stock_st(ts_code=None, trade_date=None, start_date=None, end_date=None, fields=None, limit=None, offset=None)`
  - Local sync table: `stock_st`
  - ST and delisting-risk flags.

- `suspend_d(ts_code=None, trade_date=None, start_date=None, end_date=None, fields=None, limit=None, offset=None)`
  - Local sync table: `suspend_d`
  - Daily suspension records.

- `stk_limit(ts_code=None, trade_date=None, start_date=None, end_date=None, fields=None, limit=None, offset=None)`
  - Local sync table: `stk_limit`
  - Daily up/down price limits.

- `index_daily(ts_code=None, trade_date=None, start_date=None, end_date=None, fields=None, limit=None, offset=None)`
  - Local sync table: `index_daily`
  - Broad index daily bars.

- `index_weight(index_code=None, trade_date=None, start_date=None, end_date=None, fields=None, limit=None, offset=None)`
  - Local sync table: `index_weight`
  - CSI index constituent weights.

- `universe(universe=None, ts_code=None, trade_date=None, start_date=None, end_date=None, fields=None, limit=None, offset=None)`
  - Local build target: `build-universe`
  - Available universes include `univ_research_base`, `univ_trade_base`, `univ_trade_hs300`, `univ_trade_zz500`, and `univ_trade_zz1000` when built.

- `etf_basic(ts_code=None, index_code=None, list_date=None, list_status=None, exchange=None, mgr=None, mgr_name=None, fields=None, limit=None, offset=None)`
  - Local sync table: `etf_basic`
  - ETF basic information, including tracking index, manager, listing status, and fund type.
  - `mgr` and `mgr_name` both filter the stored `mgr_name` column. If both are provided, they must match.

- `fund_adj(ts_code=None, trade_date=None, start_date=None, end_date=None, fields=None, limit=None, offset=None)`
  - Local sync table: `fund_adj`
  - Fund adjustment factors used for adjusted fund price calculations.

- `pro_bar(ts_code, start_date=None, end_date=None, asset="E", adj=None, freq="D", trade_date=None, ma=None, limit=None, offset=None)`
  - Uses local `daily` and `adj_factor`.
  - Supports only `asset="E"` and `freq="D"`.
  - `adj` must be `None`, `"qfq"`, or `"hfq"`.
  - Moving averages via `ma` are not supported locally.

## Industry

- `index_classify(level=None, src=None, fields=None, limit=None, offset=None)`
  - Local sync table: `industry`
  - Shenwan industry classification.

- `index_member_all(l1_code=None, ts_code=None, is_new=None, fields=None, limit=None, offset=None)`
  - Local sync table: `industry`
  - Shenwan industry membership.

- `ci_index_member(l1_code=None, ts_code=None, is_new=None, fields=None, limit=None, offset=None)`
  - Local sync table: `ci_member`
  - China Securities Index industry membership.

## Futures

- `fut_basic(ts_code=None, exchange=None, fut_type=None, fut_code=None, fields=None, limit=None, offset=None)`
  - Local sync table: `fut_basic`
  - Futures contract specs.
  - `fut_type` is accepted for API compatibility but is not currently filtered.

- `fut_daily(ts_code=None, trade_date=None, start_date=None, end_date=None, fields=None, limit=None, offset=None)`
  - Local sync table: `fut_daily`
  - Futures daily bars and open interest.

- `fut_holding(trade_date=None, symbol=None, start_date=None, end_date=None, exchange=None, fields=None, limit=None, offset=None)`
  - Local sync table: `fut_holding`
  - Broker long/short position rankings.

- `fut_wsr(trade_date=None, symbol=None, start_date=None, end_date=None, exchange=None, fields=None, limit=None, offset=None)`
  - Local sync table: `fut_wsr`
  - Warehouse stock receipt data.

- `fut_settle(ts_code=None, trade_date=None, start_date=None, end_date=None, exchange=None, fields=None, limit=None, offset=None)`
  - Local sync table: `fut_settle`
  - Daily settlement data.

- `fut_mapping(ts_code=None, trade_date=None, start_date=None, end_date=None, fields=None, limit=None, offset=None)`
  - Local sync table: `fut_mapping`
  - Main/continuous contract mapping.

- `ft_limit(ts_code=None, trade_date=None, start_date=None, end_date=None, exchange=None, fields=None, limit=None, offset=None)`
  - Local sync table: `ft_limit`
  - Futures price limits.

- `fut_weekly(ts_code=None, trade_date=None, start_date=None, end_date=None, exchange=None, fields=None, limit=None, offset=None)`
  - Local sync table: `fut_weekly`
  - Futures weekly bars.

- `fut_monthly(ts_code=None, trade_date=None, start_date=None, end_date=None, exchange=None, fields=None, limit=None, offset=None)`
  - Local sync table: `fut_monthly`
  - Futures monthly bars.

- `fut_index_daily(ts_code=None, trade_date=None, start_date=None, end_date=None, fields=None, limit=None, offset=None)`
  - Local sync table: `fut_index_daily`
  - Continuous main contract index daily bars.

- `fut_weekly_detail(exchange=None, prd=None, start_date=None, end_date=None, fields=None, limit=None, offset=None)`
  - Local sync table: `fut_weekly_detail`
  - Exchange weekly long/short participant detail.

## Options

- `opt_basic(ts_code=None, exchange=None, opt_code=None, call_put=None, name=None, list_date=None, limit=None, offset=None, fields=None)`
  - Local sync table: `opt_basic`
  - Option contract specs.

- `opt_daily(ts_code=None, trade_date=None, start_date=None, end_date=None, exchange=None, limit=None, offset=None, fields=None)`
  - Local sync table: `opt_daily`
  - Option daily bars, settlement, and open interest.

## Unsupported Tushare Areas

zer0share does not currently expose local finance statements, macro data, realtime quotes, news, announcements, funds, Hong Kong stocks, or US stocks. If users ask for these, state that the local skill cannot answer from current synced zer0share data.
