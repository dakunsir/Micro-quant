---
name: microshare-data
description: 面向中文自然语言的 Microshare 本地金融数据查询技能。用于把股票、ETF、指数、行业、期货、期权、股票池、复权行情等请求转成 Microshare 的 Tushare-like 本地查询流程。适用于已经用 Microshare 同步到本地 Parquet/DuckDB 数据的 A 股、ETF、期货和期权研究场景；查询不访问在线 Tushare，不消耗 Tushare 积分。
---

# Microshare-data

Use this skill to answer Chinese financial data requests with local Microshare data.
The query API intentionally looks like Tushare Pro, but the data source is local Parquet files queried through DuckDB.

## Core Rules

- Use `from microshare import pro_api` as the default entry point.
- Do not call online Tushare for query tasks.
- Do not require `TUSHARE_TOKEN` for local queries.
- Assume data must already be synced locally. If a table is missing, tell the user which `python main.py sync --table ...` or `python main.py build-universe` command is needed.
- Use `YYYYMMDD` for `trade_date`, `start_date`, and `end_date`.
- Do not combine `trade_date` with `start_date` or `end_date`.
- Prefer small, targeted queries first; add fields and ranges only when needed.
- Never fabricate missing market, financial, news, macro, or real-time data. Microshare only supports the local interfaces present in the current repository.

## Environment Check

Before running a query, verify the local project can import microshare:

```bash
uv run python -c "from microshare import pro_api; print(type(pro_api()).__name__)"
```

If this fails, report the import/config error directly. If it succeeds but a query raises `FileNotFoundError`, the data has not been synced yet.

## Basic Query Pattern

```python
from microshare import pro_api

pro = pro_api()

df = pro.daily(
    ts_code="000001.SZ",
    start_date="20240101",
    end_date="20240131",
)
```

For dynamic API names, use:

```python
df = pro.query(
    "daily",
    ts_code="000001.SZ",
    start_date="20240101",
    end_date="20240131",
)
```

The bundled script can run the same pattern from shell:

```bash
uv run python skills/microshare-data/scripts/query_local.py daily \
  --params '{"ts_code":"000001.SZ","start_date":"20240101","end_date":"20240131"}' \
  --head 10
```

## Intent Handling

Map user language to local interfaces:

- 股票基础资料: `stock_basic`
- 交易日历: `trade_cal`
- 股票行情: `daily`, `pro_bar`, `adj_factor`
- 估值和每日指标: `daily_basic`
- ST、停牌、涨跌停: `stock_st`, `suspend_d`, `stk_limit`
- 指数行情和成分: `index_daily`, `index_weight`
- ETF: `etf_basic`, `etf_index`, `fund_daily`, `fund_adj`, `etf_share_size`
- 行业分类和成分: `index_classify`, `index_member_all`, `ci_index_member`
- 股票池: `universe`
- 期货: `fut_basic`, `fut_daily`, `fut_holding`, `fut_wsr`, `fut_settle`, `fut_mapping`, `ft_limit`, `fut_weekly`, `fut_monthly`, `fut_index_daily`, `fut_weekly_detail`
- 期权: `opt_basic`, `opt_daily`

For exact parameters and supported interfaces, read `references/api.md`.

## Defaults

- "最近走势": use the latest locally available 20 trading days if you can infer the available range, otherwise ask for a date range.
- "这段时间": default to roughly 3 months when a date range is not specified and local data coverage is known.
- "今年以来": use January 1 of the current year through the latest locally available date.
- "复权行情": use `pro_bar(..., adj="qfq")` unless the user asks for `hfq` or no adjustment.
- "行业": prefer Shenwan via `index_classify` / `index_member_all` unless the user asks for China Securities Index via `ci_index_member`.

If the available local data range is unknown, query a small table/date range first or ask for a concrete date range.

## Output Contract

Unless the user asks only for raw data, respond with:

1. One-line conclusion.
2. Data range and local interface used.
3. Key table or metrics.
4. Caveats: missing synced tables, empty results, non-trading days, unsupported interfaces, or local snapshot limitations.

## Empty Result Handling

An empty DataFrame is not automatically an error. Check and explain likely causes:

- table not synced for that date range;
- non-trading day;
- stock, futures, or option contract not listed during that period;
- filters too narrow;
- requested interface is not implemented by Microshare.
