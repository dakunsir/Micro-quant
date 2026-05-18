from __future__ import annotations

import argparse
import sys

from zer0share import pro_api


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def run_examples(
    ts_code: str,
    start_date: str,
    end_date: str,
    trade_date: str,
    index_code: str,
    index_start_date: str,
    index_end_date: str,
) -> None:
    pro = pro_api()

    basic = pro.stock_basic(
        ts_code=ts_code,
        fields="ts_code,symbol,name,market,exchange,list_status,list_date,delist_date",
    )
    _print_frame("stock_basic", basic)

    trade_cal = pro.trade_cal(
        exchange="SSE",
        start_date=start_date,
        end_date=end_date,
        is_open="1",
        fields="exchange,cal_date,is_open,pretrade_date",
    )
    _print_frame("trade_cal", trade_cal)

    daily = pro.daily(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        fields="ts_code,trade_date,open,high,low,close,vol,amount",
    )
    _print_frame("daily", daily)

    adj_factor = pro.adj_factor(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        fields="ts_code,trade_date,adj_factor",
    )
    _print_frame("adj_factor", adj_factor)

    daily_basic = pro.daily_basic(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        fields="ts_code,trade_date,total_mv,circ_mv,turnover_rate,pe,pb",
    )
    _print_frame("daily_basic", daily_basic)

    stock_st = pro.stock_st(
        start_date=start_date,
        end_date=end_date,
        fields="ts_code,name,trade_date,type,type_name",
    )
    _print_frame("stock_st", stock_st)

    suspend_d = pro.suspend_d(
        start_date=start_date,
        end_date=end_date,
        fields="ts_code,trade_date,suspend_timing,suspend_type",
    )
    _print_frame("suspend_d", suspend_d)

    stk_limit = pro.stk_limit(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        fields="trade_date,ts_code,pre_close,up_limit,down_limit",
    )
    _print_frame("stk_limit", stk_limit)

    index_weight = pro.index_weight(
        index_code=index_code,
        start_date=index_start_date,
        end_date=index_end_date,
        fields="index_code,con_code,trade_date,weight",
    )
    _print_frame("index_weight", index_weight)

    qfq = pro.pro_bar(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        adj="qfq",
    )
    _print_frame("pro_bar_qfq", qfq)

    hfq = pro.pro_bar(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        adj="hfq",
    )
    _print_frame("pro_bar_hfq", hfq)

    by_query = pro.query(
        "pro_bar",
        ts_code=ts_code,
        trade_date=trade_date,
        adj="qfq",
    )
    _print_frame("query_pro_bar_qfq_by_trade_date", by_query)

    index_by_query = pro.query(
        "index_weight",
        index_code=index_code,
        start_date=index_start_date,
        end_date=index_end_date,
        fields="index_code,con_code,trade_date,weight",
    )
    _print_frame("query_index_weight", index_by_query)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test the local Tushare-like query API against synced Parquet data."
    )
    parser.add_argument("--ts-code", default="000001.SZ")
    parser.add_argument("--start-date", default="20260511")
    parser.add_argument("--end-date", default="20260515")
    parser.add_argument("--trade-date", default="20260515")
    parser.add_argument("--index-code", default="399300.SZ")
    parser.add_argument("--index-start-date", default="20260401")
    parser.add_argument("--index-end-date", default="20260518")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_examples(
            ts_code=args.ts_code,
            start_date=args.start_date,
            end_date=args.end_date,
            trade_date=args.trade_date,
            index_code=args.index_code,
            index_start_date=args.index_start_date,
            index_end_date=args.index_end_date,
        )
    except FileNotFoundError as exc:
        print(f"Missing local data: {exc}", file=sys.stderr)
        print("Run the relevant sync command first, for example:", file=sys.stderr)
        print("  uv run python main.py sync --all", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
