# zer0share

![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Stars](https://img.shields.io/github/stars/zer0quant/zer0share)

> **zer0share** — A local data pipeline for Chinese A-shares, ETFs, futures & options.  
> Pulls data from Tushare Pro, stores as Parquet partitions,  
> queries via DuckDB, with incremental sync & APScheduler automation.

> 我在公众号「极客投研笔记」记录这个项目的设计过程、踩坑记录和后续扩展。  
> 如果你对 AI + 量化投研、本地量化数据系统、因子研究工作流感兴趣，欢迎关注。

A 股、ETF、期货、期权数据本地化管道，基于 [Tushare Pro](https://tushare.pro) 拉取数据，以 Parquet 分区存储，DuckDB 提供快速本地查询，支持增量同步与定时调度。

## 为什么用 zer0share？

直接调 Tushare Pro 做研究有两个痛点：每次查询消耗积分，批量回测时 API 限速拖慢迭代。zer0share 把数据落到本地，查询走 DuckDB，既省积分又快。

| | 直接调 Tushare Pro | zer0share 本地查询 |
|---|---|---|
| 积分消耗 | 每次请求消耗 | 零消耗 |
| 网络依赖 | 必须联网 | 离线可用 |
| 查询速度 | 受 API 限速 | DuckDB 本地毫秒级 |
| 数据一致性 | 取决于调用时机 | 快照固定，结果可复现 |

## 特性

- **A 股数据**：交易日历、基础信息、日线、复权因子、每日指标、ST、停复牌、涨跌停、指数成分、申万/中信行业
- **ETF 数据**：ETF 基础信息、本地查询与专题存储
- **期货 & 期权数据**：期货合约、日线、持仓排名、仓单、结算、主连映射；期权合约与日线行情
- **本地优先存储**：Parquet 分区文件 + DuckDB 元数据，无需数据库服务
- **Tushare-like 查询**：本地 `pro_api()` 直接返回 DataFrame，不消耗 Tushare 积分
- **复权行情**：本地 `pro_bar()` 支持不复权、前复权（qfq）和后复权（hfq）
- **股票池构建**：支持研究基础池、交易基础池、沪深300/中证500/中证1000交易池
- **自动化运维**：APScheduler 定时同步，支持企业微信失败告警

## 环境要求

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- Tushare Pro Token（基础行情需积分 ≥ 2000；`stock_st` 需积分 ≥ 3000；ETF 基础信息和 ETF 份额规模需积分 ≥ 8000；ETF 日线行情需积分 ≥ 5000；基金复权因子需积分 ≥ 600，5000 积分以上频次更高；指数公告 `idx_anns` 需积分 ≥ 6000；中信行业成分、`opt_basic` 需积分 ≥ 5000；部分期货扩展数据需积分 ≥ 5000）

## 快速开始

### 1. 克隆并安装依赖

```bash
git clone https://github.com/zer0quant/zer0share.git
cd zer0share
uv sync
```

### 2. 配置

```bash
cp config/settings.example.toml config/settings.toml
```

编辑 `config/settings.toml`，填入 Tushare Token：

```toml
[tushare]
token = "your_tushare_token_here"
```

### 3. 首次同步

```bash
# 一键同步全部
uv run python main.py sync --all

# 或逐步执行（顺序不可颠倒）

# ── 股票核心（必选）────────────────────────────────────────────────
uv run python main.py sync --table trade_cal    # 交易日历（必须最先）
uv run python main.py sync --table basic        # 股票基础信息
uv run python main.py sync --table daily_kline  # 日线行情（依赖交易日历）
uv run python main.py sync --table adj_factor   # 复权因子（依赖交易日历）
uv run python main.py sync --table daily_basic  # 每日指标：总市值、流通市值等
uv run python main.py sync --table stock_st     # 每日 ST 股票列表
uv run python main.py sync --table suspend_d    # 每日停牌列表
uv run python main.py sync --table stk_limit    # 每日涨跌停价格
uv run python main.py sync --table index_weight # 沪深300/中证500/中证1000成分
uv run python main.py sync --table index_daily  # 宽基指数日线行情
uv run python main.py sync --table idx_anns     # 指数公司公告（自然日同步）
uv run python main.py sync --table industry     # 申万行业分类 + 成分映射
uv run python main.py sync --table ci_member    # 中信行业成分映射

# ── ETF 专题（可选）──────────────────────────────────────────────
uv run python main.py sync --table etf_basic    # ETF 基础信息
uv run python main.py sync --table etf_index    # ETF 基准指数列表
uv run python main.py sync --table fund_daily   # ETF 日线行情（需积分 >= 5000，8000 积分频次更高）
uv run python main.py sync --table fund_adj     # 基金复权因子（需积分 >= 600，5000 积分以上频次更高）
uv run python main.py sync --table etf_share_size  # ETF 份额规模（需积分 >= 8000，通常次日 08:30 后更新）
uv run python main.py sync --table etf_sh_cons  # 上交所 ETF 每日持仓组合（需积分 >= 8000）

# ── 期货扩展（可选，需积分 ≥ 5000）────────────────────────────────
uv run python main.py sync --table fut_basic          # 期货合约基础信息
uv run python main.py sync --table fut_daily          # 期货日线行情
uv run python main.py sync --table fut_holding        # 期货持仓排名
uv run python main.py sync --table fut_wsr            # 期货仓单日报
uv run python main.py sync --table fut_settle         # 期货结算参数
uv run python main.py sync --table fut_mapping        # 期货主力与连续合约映射
uv run python main.py sync --table ft_limit           # 期货涨跌停价格
uv run python main.py sync --table fut_weekly         # 期货周线行情
uv run python main.py sync --table fut_monthly        # 期货月线行情
uv run python main.py sync --table fut_index_daily    # 期货指数日线行情
uv run python main.py sync --table fut_weekly_detail  # 期货交易所周度明细

# ── 期权扩展（可选，需积分 ≥ 5000）────────────────────────────────
uv run python main.py sync --table opt_basic          # 期权合约基础信息
uv run python main.py sync --table opt_daily          # 期权日线行情
```

首次验证建议先同步一个小区间，确认 Tushare 权限和字段可用后再全量回填：

```bash
uv run python main.py sync --table daily_basic --start-date 20240101 --end-date 20240131
uv run python main.py sync --table stock_st --start-date 20240101 --end-date 20240131
uv run python main.py sync --table suspend_d --start-date 20240101 --end-date 20240131
uv run python main.py sync --table stk_limit --start-date 20240101 --end-date 20240131
uv run python main.py sync --table index_weight --start-date 20240101 --end-date 20240131
uv run python main.py sync --table fut_daily --start-date 20240101 --end-date 20240131
uv run python main.py sync --table ft_limit --start-date 20240101 --end-date 20240131
uv run python main.py sync --table opt_daily --start-date 20240101 --end-date 20240131
```

### 4. 构建股票池

同步完对应交易日的数据后，可以构建股票池。默认按交易日从 2016-01-01 构建到今天，并跳过已存在的完整分区：

```bash
uv run python main.py build-universe
```

也可以指定区间或构建单日：

```bash
uv run python main.py build-universe --start-date 20240101 --end-date 20240131
uv run python main.py build-universe --date 20240131
```

生成的股票池包括：

| 股票池 | 说明 |
|------|------|
| `univ_research_base` | 基础研究池，用于中性化、标准化、因子横截面分析 |
| `univ_trade_base` | 基础交易池，用于全 A 候选选股 |
| `univ_trade_hs300` | 沪深300成分中满足交易过滤条件的股票池 |
| `univ_trade_zz500` | 中证500成分中满足交易过滤条件的股票池 |
| `univ_trade_zz1000` | 中证1000成分中满足交易过滤条件的股票池 |

`univ_research_base` 过滤规则：

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

### 5. 查看同步状态

```bash
uv run python main.py status
```

### 6. 定时调度

**推荐：systemd 服务（服务器常驻）**

```bash
# 安装并启用服务
sudo cp scripts/zer0share-scheduler.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable zer0share-scheduler
sudo systemctl start zer0share-scheduler

# 查看状态
sudo systemctl status zer0share-scheduler

# 查看实时日志
journalctl -u zer0share-scheduler -f

# 修改 settings.toml 后重启生效
sudo systemctl restart zer0share-scheduler
```

**手动启动（调试用）**

```bash
uv run python main.py scheduler start
```

## 数据质检

数据质检仅在本地运行，不访问外部服务。支持以下命令：

```bash
uv run python main.py quality check --all --mode full --start-date 20200101 --end-date 20241231
uv run python main.py quality check --market stock --mode daily
uv run python main.py quality check --table daily_kline --mode daily --date 20240701
```

终端输出的是表级摘要，详细报告写入 `reports/quality/YYYYMMDD_HHMMSS/`。

## 本地查询 API

同步完成后，可以在研究代码中使用类似 Tushare Pro 的本地 Python API 查询数据。查询只读取本地 Parquet 文件，通过 DuckDB 执行，不会访问 Tushare，也不会消耗积分。

仓库内置 AI Skill：`skills/zer0share-data`。支持让 Codex、Claude Code、OpenClaw 等智能体把中文自然语言数据请求转成 `zer0share` 本地查询流程。

```python
from zer0share import pro_api

pro = pro_api()

basic = pro.stock_basic(list_status="L")
cal = pro.trade_cal(exchange="SSE", start_date="20240101", end_date="20240131")
daily = pro.daily(ts_code="000001.SZ", start_date="20240101", end_date="20240331")
adj = pro.adj_factor(ts_code="000001.SZ", start_date="20240101", end_date="20240331")
daily_basic = pro.daily_basic(trade_date="20240131", fields="ts_code,trade_date,total_mv")
st = pro.stock_st(trade_date="20240131")
suspend = pro.suspend_d(trade_date="20240131")
limit = pro.stk_limit(trade_date="20240131")
hs300 = pro.index_weight(index_code="399300.SZ", start_date="20240101", end_date="20240131")
idx_anns = pro.idx_anns(
    src="中证指数",
    start_date="20260401",
    end_date="20260430",
    fields="ann_date,title,source,type",
)
etf_basic = pro.etf_basic(list_status="L", exchange="SH")
etf_index = pro.etf_index(ts_code="000300.SH")
fund_daily = pro.fund_daily(
    ts_code="510330.SH",
    start_date="20250101",
    end_date="20250618",
    fields="trade_date,open,high,low,close,vol,amount",
)
fund_adj = pro.fund_adj(
    ts_code="513100.SH",
    start_date="20190101",
    end_date="20190926",
    fields="ts_code,trade_date,adj_factor,discount_rate",
)
etf_share_size = pro.etf_share_size(
    ts_code="510330.SH",
    start_date="20250101",
    end_date="20251224",
    fields="trade_date,ts_code,etf_name,total_share,total_size,exchange",
)
etf_sh_cons = pro.etf_sh_cons(
    trade_date="20260615",
    ts_code="517030.SH",
    fields="trade_date,ts_code,con_code,con_name,qty,sub_flag,cpr,rdr,sca,exchange",
)

# 指数日线行情（用于对冲基准收益率）
idx_daily = pro.index_daily(ts_code="000300.SH", start_date="20240101", end_date="20240131")

# 行业数据（用于行业中性化）
sw_industries = pro.index_classify(level="L1", src="SW2021")       # 申万一级行业列表
sw_member = pro.index_member_all(ts_code="000001.SZ", is_new="Y")  # 查股票所属申万行业
ci_member = pro.ci_index_member(ts_code="000001.SZ", is_new="Y")   # 查股票所属中信行业

qfq = pro.pro_bar(
    ts_code="000001.SZ",
    start_date="20240101",
    end_date="20240331",
    adj="qfq",
)

# 股票池
pool = pro.universe("univ_trade_hs300", trade_date="20240131")   # 某日沪深300交易池

# 期货数据
fut_contracts = pro.fut_basic(exchange="SHFE")                                    # 上期所期货合约列表
fut_bar = pro.fut_daily(ts_code="RB2410.SHFE", start_date="20240101", end_date="20240331")
fut_holding = pro.fut_holding(trade_date="20240131", exchange="SHFE")             # 某日持仓排名
fut_mapping = pro.fut_mapping(ts_code="RB.SHFE", start_date="20240101", end_date="20240331")  # 主连映射
fut_weekly = pro.fut_weekly(ts_code="RB2501.SHFE", start_date="20240101", end_date="20240331")

# 期权数据
opt_contracts = pro.opt_basic(exchange="SSE", call_put="C")           # 上交所认购期权合约列表
opt_bar = pro.opt_daily(ts_code="10004462.SH", start_date="20240101", end_date="20240131")
opt_snapshot = pro.opt_daily(trade_date="20240102", exchange="SSE")   # 某日全部上交所期权行情
```

支持的本地查询方法：

| 方法 | 说明 |
|------|------|
| `stock_basic` | 查询已同步的股票基础信息 |
| `trade_cal` | 查询已同步的交易日历 |
| `daily` | 查询已同步的 A 股日线行情 |
| `adj_factor` | 查询已同步的复权因子 |
| `daily_basic` | 查询已同步的每日指标 |
| `stock_st` | 查询已同步的每日 ST 股票列表 |
| `suspend_d` | 查询已同步的每日停复牌信息 |
| `stk_limit` | 查询已同步的每日涨跌停价格 |
| `index_weight` | 查询已同步的指数成分和权重 |
| `index_daily` | 查询已同步的宽基指数日线行情（12个指数） |
| `idx_anns` | 查询已同步的指数公司公告（按 `ann_date` 分区） |
| `index_classify` | 查询申万行业分类树（L1/L2/L3） |
| `index_member_all` | 查询申万股票-行业映射（支持历史变更） |
| `ci_index_member` | 查询中信股票-行业映射（支持历史变更） |
| `etf_basic` | 查询已同步的 ETF 基础信息 |
| `etf_index` | 查询已同步的 ETF 基准指数列表 |
| `fund_daily` | 查询已同步的 ETF 日线行情 |
| `fund_adj` | 查询已同步的基金复权因子 |
| `etf_share_size` | 查询已同步的 ETF 份额规模 |
| `etf_sh_cons` | 查询已同步的上交所 ETF 每日持仓组合 |
| `pro_bar` | 查询本地 A 股日线行情，支持不复权、前复权（qfq）和后复权（hfq） |
| `universe` | 查询已构建的股票池（支持按池名称、ts_code、日期过滤） |
| `fut_basic` | 查询已同步的期货合约基础信息（支持按交易所、fut_code 过滤） |
| `fut_daily` | 查询已同步的期货日线行情 |
| `fut_holding` | 查询已同步的期货持仓排名 |
| `fut_wsr` | 查询已同步的期货仓单日报 |
| `fut_settle` | 查询已同步的期货结算参数 |
| `fut_mapping` | 查询已同步的期货主力与连续合约映射 |
| `ft_limit` | 查询已同步的期货涨跌停价格 |
| `fut_weekly` | 查询已同步的期货周线行情 |
| `fut_monthly` | 查询已同步的期货月线行情 |
| `fut_index_daily` | 查询已同步的期货指数日线行情 |
| `fut_weekly_detail` | 查询已同步的期货交易所周度明细 |
| `opt_basic` | 查询已同步的期权合约基础信息（支持按交易所、call_put、opt_code 过滤） |
| `opt_daily` | 查询已同步的期权日线行情（支持按交易所过滤） |
| `query` | 按接口名分发，例如 `pro.query("daily", ...)` |

运行冒烟测试。完整示例清单和默认参数见 [examples/README.md](examples/README.md)。

```bash
# 股票示例
uv run python examples/stock/basic_query_smoke.py
uv run python examples/stock/daily_query_smoke.py
uv run python examples/stock/adj_factor_query_smoke.py

# ETF 示例
uv run python examples/etf/etf_basic_query_smoke.py
uv run python examples/etf/etf_index_query_smoke.py
uv run python examples/etf/fund_daily_query_smoke.py
uv run python examples/etf/etf_share_size_query_smoke.py
uv run python examples/etf/etf_sh_cons_query_smoke.py

# 指数示例
uv run python examples/index/index_daily_query_smoke.py
uv run python examples/index/index_weight_query_smoke.py
uv run python examples/index/idx_anns_query_smoke.py

# 期货示例
uv run python examples/futures/fut_basic_query_smoke.py
uv run python examples/futures/fut_daily_query_smoke.py
uv run python examples/futures/fut_holding_query_smoke.py
uv run python examples/futures/fut_settle_query_smoke.py
uv run python examples/futures/fut_weekly_monthly_query_smoke.py
uv run python examples/futures/ft_limit_query_smoke.py

# 期权示例
uv run python examples/options/opt_basic_query_smoke.py
uv run python examples/options/opt_daily_query_smoke.py
```

## 数据存储结构

目录按 Tushare 数据分类命名：`stock/`（股票数据）、`etf/`（ETF专题）、`index/`（指数专题）、`futures/`（期货数据）、`options/`（期权数据）。

```
data/
├── stock/                              # 股票数据
│   ├── trade_cal/
│   │   ├── exchange=SSE/data.parquet
│   │   ├── exchange=SZSE/data.parquet
│   │   ├── exchange=CFFEX/data.parquet
│   │   ├── exchange=SHFE/data.parquet
│   │   ├── exchange=DCE/data.parquet
│   │   ├── exchange=CZCE/data.parquet
│   │   ├── exchange=INE/data.parquet
│   │   └── exchange=GFEX/data.parquet
│   ├── basic/
│   │   └── data.parquet
│   ├── daily_kline/
│   │   └── date=YYYYMMDD/data.parquet
│   ├── adj_factor/
│   │   └── date=YYYYMMDD/data.parquet
│   ├── daily_basic/
│   │   └── date=YYYYMMDD/data.parquet
│   ├── stock_st/
│   │   └── date=YYYYMMDD/data.parquet
│   ├── suspend_d/
│   │   └── date=YYYYMMDD/data.parquet
│   ├── stk_limit/
│   │   └── date=YYYYMMDD/data.parquet
│   ├── industry/
│   │   ├── sw_classify/data.parquet   # 申万行业分类树
│   │   ├── sw_member/data.parquet     # 申万股票-行业映射（全量历史）
│   │   └── ci_member/data.parquet     # 中信股票-行业映射（全量历史）
│   └── universe/
│       ├── name=univ_research_base/date=YYYYMMDD/data.parquet
│       ├── name=univ_trade_base/date=YYYYMMDD/data.parquet
│       ├── name=univ_trade_hs300/date=YYYYMMDD/data.parquet
│       ├── name=univ_trade_zz500/date=YYYYMMDD/data.parquet
│       └── name=univ_trade_zz1000/date=YYYYMMDD/data.parquet
├── etf/                                # ETF专题
│   ├── etf_basic/
│   │   └── data.parquet
│   ├── etf_index/
│   │   └── data.parquet
│   ├── fund_daily/
│   │   └── date=YYYYMMDD/data.parquet
│   ├── fund_adj/
│   │   └── date=YYYYMMDD/data.parquet
│   ├── etf_share_size/
│   │   └── date=YYYYMMDD/data.parquet
│   └── etf_sh_cons/
│       └── date=YYYYMMDD/data.parquet
├── index/                              # 指数专题
│   ├── index_daily/
│   │   └── date=YYYYMMDD/data.parquet  # 含当日全部12个宽基指数
│   ├── index_weight/
│   │   └── index_code=*/date=YYYYMMDD/data.parquet
│   └── idx_anns/
│       └── date=YYYYMMDD/data.parquet  # 指数公告
├── futures/                            # 期货数据
│   ├── fut_basic/data.parquet          # 全量，每次覆盖
│   ├── fut_daily/date=YYYYMMDD/data.parquet
│   ├── fut_holding/date=YYYYMMDD/data.parquet
│   ├── fut_wsr/date=YYYYMMDD/data.parquet
│   ├── fut_settle/date=YYYYMMDD/data.parquet
│   ├── fut_mapping/date=YYYYMMDD/data.parquet
│   ├── ft_limit/date=YYYYMMDD/data.parquet
│   ├── fut_weekly/date=YYYYMMDD/data.parquet
│   ├── fut_monthly/date=YYYYMMDD/data.parquet
│   ├── fut_index_daily/date=YYYYMMDD/data.parquet
│   └── fut_weekly_detail/date=YYYYMMDD/data.parquet
└── options/                            # 期权数据
    ├── opt_basic/data.parquet          # 全量，每次覆盖
    └── opt_daily/date=YYYYMMDD/data.parquet
db/
└── meta.duckdb                         # 同步记录 + 交易日历索引
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `sync --table trade_cal` | 增量同步交易日历（SSE、SZSE、CFFEX、SHFE、DCE、CZCE、INE、GFEX） |
| `sync --table basic` | 同步股票基础信息 |
| `sync --table daily_kline` | 增量同步日线行情 |
| `sync --table adj_factor` | 增量同步复权因子 |
| `sync --table daily_basic` | 增量同步每日指标 |
| `sync --table stock_st` | 增量同步每日 ST 股票列表 |
| `sync --table suspend_d` | 增量同步每日停复牌信息 |
| `sync --table stk_limit` | 增量同步每日涨跌停价格 |
| `sync --table index_weight` | 增量同步指数成分和权重 |
| `sync --table index_daily` | 增量同步12个宽基指数日线行情 |
| `sync --table idx_anns` | 增量同步指数公司公告（自然日同步） |
| `sync --table industry` | 同步申万行业分类 + 成分映射（全量覆盖） |
| `sync --table ci_member` | 同步中信行业成分映射（全量覆盖） |
| `sync --table etf_basic` | 同步 ETF 基础信息 |
| `sync --table etf_index` | 同步 ETF 基准指数列表 |
| `sync --table fund_daily` | 同步 ETF 日线行情 |
| `sync --table fund_adj` | 同步基金复权因子 |
| `sync --table etf_share_size` | 同步 ETF 份额规模 |
| `sync --table etf_sh_cons` | 同步上交所 ETF 每日持仓组合 |
| `sync --table fut_basic` | 同步期货合约基础信息 |
| `sync --table fut_daily` | 增量同步期货日线行情 |
| `sync --table fut_holding` | 增量同步期货持仓排名 |
| `sync --table fut_wsr` | 增量同步期货仓单日报 |
| `sync --table fut_settle` | 增量同步期货结算参数 |
| `sync --table fut_mapping` | 增量同步期货主力与连续合约映射 |
| `sync --table ft_limit` | 增量同步期货涨跌停价格 |
| `sync --table fut_weekly` | 增量同步期货周线行情 |
| `sync --table fut_monthly` | 增量同步期货月线行情 |
| `sync --table fut_index_daily` | 增量同步期货指数日线行情 |
| `sync --table fut_weekly_detail` | 增量同步期货交易所周度明细 |
| `sync --table opt_basic` | 同步期权合约基础信息（全量覆盖） |
| `sync --table opt_daily` | 增量同步期权日线行情 |
| `sync --all` | 按顺序同步全部 |
| `sync --stock` | 按顺序同步股票核心与指数、行业相关表 |
| `sync --futures` | 按顺序同步期货相关表 |
| `sync --options` | 按顺序同步期权相关表 |
| `sync --etf` | 按顺序同步 ETF 专题表 |
| `build-universe` | 从 2016-01-01 到今天增量构建 5 个股票池 |
| `build-universe --start-date YYYYMMDD --end-date YYYYMMDD` | 构建指定区间的 5 个股票池 |
| `build-universe --date YYYYMMDD` | 构建指定交易日的 5 个股票池 |
| `status` | 查看各表最后同步时间 |
| `scheduler start` | 启动定时调度 |

## 配置说明

```toml
[tushare]
token = "your_tushare_token_here"

[paths]
data_dir = "data"          # Parquet 存储目录
db_path = "db/meta.duckdb" # DuckDB 文件路径
log_path = "logs/pipeline.log"

[scheduler]
# 每个表单独配置触发时间（HH:MM），基于 Tushare 各接口实际入库时间设计
# 凌晨 — 静态参考数据（增量检查，数据已最新时零API消耗）
trade_cal         = "02:00"
basic             = "02:05"
# 盘前 — Tushare 盘前推送
stk_limit         = "09:15"   # 8:40 ready; delayed to avoid early empty responses
adj_factor        = "09:25"   # 9:15~9:20 ready
stock_st          = "09:28"   # 9:20 ready
# 收盘后第一波 — 日线行情（15:00~16:00 ready）
daily_kline       = "16:10"
# 收盘后第二波 — 每日指标及其余数据（3min 间隔，17:05~17:56）
daily_basic       = "17:05"
# ... 完整示例见 config/settings.example.toml

[notifier]
wecom_webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
enabled = false            # 填写真实 webhook_url 后改为 true
```

## 开发

```bash
# 安装开发依赖
uv sync --dev

# 运行测试
uv run pytest

# 运行单个测试文件
uv run pytest tests/test_pipeline.py -v
```

## 项目结构

```
zer0share/
├── api.py        # 本地 Tushare-like 查询 API
├── catalog.py    # 本地表结构、路径和查询规格
├── cli.py        # Click CLI 入口
├── config.py     # 配置加载
├── fetcher.py    # Tushare API 封装
├── pipeline.py   # 同步任务编排
├── query/        # 本地查询实现
├── scheduler.py  # APScheduler 定时任务
├── storage.py    # Parquet 读写 + DuckDB MetaStore
├── sync/         # 各专题同步任务
└── universe.py   # 股票池构建
tests/            # pytest 测试套件
examples/
├── stock/        # 股票本地查询冒烟测试
├── etf/          # ETF 本地查询冒烟测试
├── futures/      # 期货本地查询冒烟测试
├── index/        # 指数本地查询冒烟测试
└── options/      # 期权本地查询冒烟测试
config/
└── settings.example.toml
```

## 交流

公众号：极客投研笔记

如果你对本地量化数据系统、AI 量化投研或因子研究工作流感兴趣，可以关注公众号看后续更新。

## License

MIT
