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

每个表在 `config/settings.toml` 的 `[scheduler]` 里单独配置触发时间（`HH:MM`），默认值基于 Tushare 各接口实际入库时间设计：

```toml
[scheduler]
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
```

同步失败和质检结果可通过飞书应用消息告警。配置接收者并启用通知：

```toml
[notifier]
enabled = true

[notifier.feishu]
enabled = true
receive_id_type = "user_id"
receive_id = "YOUR_FEISHU_USER_ID"
```

运行环境还必须提供 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`。应用消息使用 skill 中的官方 `lark-oapi` 接口。

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
