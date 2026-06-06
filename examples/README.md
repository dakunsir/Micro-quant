# Examples

Run these examples from the repository root after syncing local data.

```bash
uv run python examples/local_query_api_smoke.py
```

Use a different security or date range:

```bash
uv run python examples/local_query_api_smoke.py --ts-code 600000.SH --start-date 20260511 --end-date 20260515
```

The example calls the local Tushare-like API:

- `pro.stock_basic`
- `pro.trade_cal`
- `pro.daily`
- `pro.adj_factor`
- `pro.daily_basic`
- `pro.stock_st`
- `pro.suspend_d`
- `pro.stk_limit`
- `pro.index_weight`
- `pro.universe`
- `pro.pro_bar`
- `pro.query`

It reads local Parquet data only. It does not call Tushare.

Option query smoke tests:

```bash
uv run python examples/opt_basic_query_params_smoke.py
uv run python examples/opt_daily_query_smoke.py
```

The `opt_daily` smoke test defaults to the first listed 50ETF option week:

```bash
uv run python main.py sync --table opt_daily --start-date 20150209 --end-date 20150213
uv run python examples/opt_daily_query_smoke.py
```
