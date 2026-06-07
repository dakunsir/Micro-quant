# Examples

Run these examples from the repository root after syncing local data.

## 期货冒烟测试（`examples/futures/`）

| 脚本 | 默认参数 |
|------|------|
| `fut_basic_query_smoke.py` | `--exchange SHFE` |
| `fut_daily_query_smoke.py` | `--ts-code RB2501.SHFE --start-date 20240101` |
| `fut_holding_query_smoke.py` | `--symbol CU0201 --exchange SHFE --start-date 20020107` |
| `fut_wsr_query_smoke.py` | `--symbol A --exchange DCE --start-date 20070101` |
| `fut_settle_query_smoke.py` | `--ts-code CF1201.ZCE --exchange CZCE --start-date 20120104` |
| `fut_mapping_query_smoke.py` | `--ts-code RB.SHFE --start-date 20240101` |
| `ft_limit_query_smoke.py` | `--ts-code CU0502.SHF --exchange SHFE --start-date 20050104` |
| `fut_weekly_query_smoke.py` | `--ts-code RB2501.SHFE --start-date 20240101` |
| `fut_weekly_monthly_query_smoke.py` | `--ts-code RB2501.SHFE --start-date 20240101` |
| `fut_index_daily_query_smoke.py` | `--ts-code NHCI.NH --start-date 20060104` |
| `fut_weekly_detail_query_smoke.py` | `--exchange SHFE --prd CU --start-date 20160101` |

```bash
uv run python examples/futures/fut_daily_query_smoke.py
uv run python examples/futures/fut_holding_query_smoke.py
uv run python examples/futures/fut_settle_query_smoke.py
uv run python examples/futures/fut_wsr_query_smoke.py
uv run python examples/futures/ft_limit_query_smoke.py
uv run python examples/futures/fut_index_daily_query_smoke.py
uv run python examples/futures/fut_weekly_detail_query_smoke.py
```

## 期权冒烟测试（`examples/options/`）

| 脚本 | 默认参数 |
|------|------|
| `opt_basic_query_smoke.py` | `--exchange SSE` |
| `opt_daily_query_smoke.py` | `--ts-code 10000001.SH --exchange SSE --start-date 20150209` |

```bash
uv run python examples/options/opt_basic_query_smoke.py
uv run python examples/options/opt_daily_query_smoke.py
```

所有脚本只读取本地 Parquet 文件，通过 DuckDB 执行，不访问 Tushare，不消耗积分。
