# 股票池构建

同步完对应交易日的股票核心数据后，可以构建股票池。默认按交易日从 2016-01-01 构建到今天，并跳过已存在的完整分区：

```bash
uv run python main.py build-universe
```

也可以指定区间或构建单日：

```bash
uv run python main.py build-universe --start-date 20240101 --end-date 20240131
uv run python main.py build-universe --date 20240131
```

沪深主板微盘 1000 股票池单独构建，默认从 `2016-01-01` 开始。生效日 `D` 使用前一交易日 `P` 的 `daily_basic` 和 `stock_st` 数据，筛选结果标记为 `D` 生效：

```bash
uv run python main.py build-mainboard-microcap --start-date 20160101 --end-date 20260904
uv run python main.py build-mainboard-microcap --date 20260904
```

例如，2026-09-07 的快照使用 2026-09-04 的数据。每个分区同时写入 `data.parquet` 和 `manifest.json`，manifest 记录 `source_trade_date`、`effective_trade_date`、配置版本、成员数及质量 warning。

## 生成的股票池

| 股票池 | 说明 |
|------|------|
| `univ_research_base` | 基础研究池，用于中性化、标准化、因子横截面分析 |
| `univ_trade_base` | 基础交易池，用于全 A 候选选股 |
| `univ_trade_hs300` | 沪深300成分中满足交易过滤条件的股票池 |
| `univ_trade_zz500` | 中证500成分中满足交易过滤条件的股票池 |
| `univ_trade_zz1000` | 中证1000成分中满足交易过滤条件的股票池 |
| `univ_trade_smallcap` | 基础交易池中总市值倒数 20% 的小市值股票池 |
| `hushen_mainboard_previous_day_bottom1000` | 沪深主板中上市满 120 个交易日、非 ST、按前一交易日总市值升序取前 1000 只；下一交易日生效 |

微盘股票池的代码前缀为 `600/601/603/605/000/001/002/003`，不额外加入成交额、停牌或涨跌停过滤。合格股票少于 1000 只时输出全部合格股票并在 manifest 中标记 warning。

## 过滤规则

`univ_research_base`：

- A 股普通股票
- 当前交易日已上市、未退市
- 非 ST / 非 *ST
- 上市满 6 个月
- 过去 20 个交易日日均成交额 >= 1000 万元
- 总市值排名不在全市场最后 2%

`univ_trade_base` 在 `univ_research_base` 基础上继续过滤：

- 当前交易日非停牌
- 当前交易日非一字涨停
- 当前交易日非一字跌停
- 总市值排名不在全市场最后 5%

## 查询

```python
from microshare import pro_api

pro = pro_api()
pool = pro.universe("univ_trade_hs300", trade_date="20240131")
microcap = pro.universe(
    "hushen_mainboard_previous_day_bottom1000", trade_date="20260904"
)
```
