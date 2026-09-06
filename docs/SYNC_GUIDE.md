# 数据同步指南

本文档是同步相关的完整参考：Tushare 积分要求、全部同步表清单、首次同步顺序和定时调度配置。

## Tushare 积分要求

同步数据需要 [Tushare Pro](https://tushare.pro) Token。各类数据的积分门槛：

| 数据 | 积分要求 |
|---|---|
| 基础行情（日历、基础信息、日线、复权因子、每日指标） | ≥ 2000 |
| `stock_st`（每日 ST 列表） | ≥ 3000 |
| 中信行业成分、`opt_basic`、部分期货扩展数据 | ≥ 5000 |
| ETF 日线行情 `fund_daily` | ≥ 5000（8000 积分频次更高） |
| 基金复权因子 `fund_adj` | ≥ 600（5000 积分以上频次更高） |
| 指数公告 `idx_anns` | ≥ 6000 |
| ETF 基础信息、ETF 份额规模、上交所 ETF 持仓 | ≥ 8000 |

## 首次同步

一键同步全部，或按专题分组同步：

```bash
uv run python main.py sync --all      # 全部
uv run python main.py sync --stock    # 股票核心 + 指数 + 行业
uv run python main.py sync --etf      # ETF 专题
uv run python main.py sync --futures  # 期货
uv run python main.py sync --options  # 期权
```

也可以逐表执行（顺序不可颠倒）。首次同步日线等历史数据量较大，受 Tushare 每分钟调用频次限制影响，全量回填可能需要数小时。

### 股票核心（必选）

```bash
uv run python main.py sync --table trade_cal    # 交易日历（必须最先，8 个交易所）
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
uv run python main.py sync --table sw_daily     # 申万行业指数日线行情
```

构建沪深主板微盘 1000 股票池至少需要 `basic`、交易日历、`daily_basic` 和 `stock_st`。由于股票池在下一交易日 `D` 生效并使用前一交易日 `P` 的数据，历史起点为 `2016-01-01` 时，源数据应从 `2015-12-31` 开始同步：

```bash
uv run python main.py sync --table basic
uv run python main.py sync --table trade_cal
uv run python main.py sync --table daily_basic --start-date 20151231 --end-date <latest>
uv run python main.py sync --table stock_st --start-date 20151231 --end-date <latest>
uv run python main.py build-mainboard-microcap --start-date 20160101 --end-date <latest>
```

### ETF 专题（可选）

```bash
uv run python main.py sync --table etf_basic       # ETF 基础信息
uv run python main.py sync --table etf_index       # ETF 基准指数列表
uv run python main.py sync --table fund_daily      # ETF 日线行情
uv run python main.py sync --table fund_adj        # 基金复权因子
uv run python main.py sync --table etf_share_size  # ETF 份额规模（通常次日 08:30 后更新）
uv run python main.py sync --table etf_sh_cons     # 上交所 ETF 每日持仓组合
```

### 期货扩展（可选，需积分 ≥ 5000）

```bash
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
```

### 期权扩展（可选，需积分 ≥ 5000）

```bash
uv run python main.py sync --table opt_basic          # 期权合约基础信息
uv run python main.py sync --table opt_daily          # 期权日线行情
```

### RiceQuant 分钟线（可选，需 RiceQuant 账号）

```bash
uv run python main.py sync --ricequant                          # 按顺序同步全部 RiceQuant 表
uv run python main.py sync --table ricequant_basic              # 合约基础信息
uv run python main.py sync --table ricequant_stock_minute       # 股票分钟线
uv run python main.py sync --table ricequant_etf_basic          # ETF 基础信息
uv run python main.py sync --table ricequant_etf_minute         # ETF 分钟线
```

需要在 `config/settings.toml` 的 `[ricequant]` 里配置 license key 或用户名/密码，详见 [RiceQuant 分钟线文档](ricequant.md)。

## 首次验证建议

先同步一个小区间，确认 Tushare 权限和字段可用后再全量回填：

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

## 查看同步状态

```bash
uv run python main.py status
```

## 定时调度

收盘后股票链每天在 `Asia/Shanghai` 的固定时间执行。默认时间为 18:30，按交易日历串行增量同步股票池所需数据，并构建下一交易日生效的微盘股票池：

```toml
[api]
host = "127.0.0.1"
port = 8787
default_limit = 1000
max_limit = 5000

[scheduler]
enabled = true
timezone = "Asia/Shanghai"
run_time = "18:30"
state_path = "db/scheduler/latest_run.json"
lock_path = "db/scheduler/run.lock"
```

每次运行顺序为 `trade_cal → basic → daily_kline → adj_factor → daily_basic → stock_st → suspend_d → stk_limit → 覆盖校验 → 下一交易日股票池`。六张日频表会按物理分区扫描并补齐缺失日期，已有分区直接复用。行情、复权、停牌和涨跌停表从 2015-01-01 起修复，`daily_basic` 和 `stock_st` 从 2015-12-31 起修复。当前日期不是交易日时只更新交易日历并记录 `SKIPPED`，不生成快照。任一阶段重试失败或覆盖校验不通过，会停止后续阶段、记录 `FAILED` 并发送飞书告警，下一次运行继续增量恢复。

历史行情缺失时，显式日期范围会绕过 `sync_meta` 的最新日期前沿，只复用已有分区并补齐物理缺口。首次回填按以下顺序执行：

```powershell
uv run python main.py sync --table trade_cal
uv run python main.py sync --table basic
uv run python main.py sync --table daily_kline --start-date 20150101 --end-date 20260904
uv run python main.py sync --table adj_factor --start-date 20150101 --end-date 20260904
uv run python main.py sync --table suspend_d --start-date 20150101 --end-date 20260904
uv run python main.py sync --table stk_limit --start-date 20150101 --end-date 20260904
uv run python main.py sync --table daily_basic --start-date 20151231 --end-date 20260904
uv run python main.py sync --table stock_st --start-date 20151231 --end-date 20260904
```

命令可安全重跑，已存在分区会跳过。历史回填完成后，使用 `GET /v1/status` 检查 `coverage.status=ok`、各表 `missing_partitions=0`，并以 `open_t1_ready_through` 作为 `open_t1` 评估截止日。

运行状态写入 `db/scheduler/latest_run.json`，调度锁写入 `db/scheduler/run.lock`。

同步失败和质检结果可通过飞书应用消息告警。配置接收者并启用通知：

```toml
[notifier]
enabled = true

[notifier.feishu]
enabled = true
receive_id_type = "user_id"
receive_id = "YOUR_FEISHU_USER_ID"
```

发送模块包含默认应用凭据，也可用 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 环境变量覆盖。应用消息使用 skill 中的官方 `lark-oapi` 接口。

### systemd 服务（推荐，服务器常驻）

```bash
# 安装并启用服务
sudo cp scripts/microshare-scheduler.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable microshare-scheduler
sudo systemctl start microshare-scheduler

# 查看状态
sudo systemctl status microshare-scheduler

# 查看实时日志
journalctl -u microshare-scheduler -f

# 修改 settings.toml 后重启生效
sudo systemctl restart microshare-scheduler
```

### 手动启动（调试用）

```bash
uv run python main.py scheduler start
```

### 只读查询服务

API 与调度器独立运行，启动后仅监听本机：

```bash
uv run python main.py api start
```

访问 `http://127.0.0.1:8787/docs` 查看 OpenAPI。服务只提供本地数据查询、健康检查和状态读取，不提供同步、构建、任意 SQL 或配置修改接口。

服务器常驻时可单独安装 API 服务：

```bash
sudo cp scripts/microshare-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now microshare-api
sudo systemctl status microshare-api
```
