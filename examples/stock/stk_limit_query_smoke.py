from __future__ import annotations

import argparse
import sys

from micro import pro_api


FIELDS = "trade_date,ts_code,pre_close,up_limit,down_limit"


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def _pick_sample(pro, trade_date: str):
    sample = pro.stk_limit(trade_date=trade_date, limit=1, fields=FIELDS)
    if sample.empty:
        raise ValueError(
            f"no stk_limit data found for trade_date={trade_date}; "
            "data starts from 2007-01-04 — try a more recent trading date"
        )
    return sample.iloc[0]


def run_smoke(ts_code: str, trade_date: str, start_date: str, end_date: str,
              offset: int, limit: int) -> None:
    pro = pro_api()
    sample = _pick_sample(pro, trade_date=trade_date)
    ts_code_sample = sample["ts_code"]

    print("Sample values")
    print(f"ts_code(sample)={ts_code_sample}  trade_date={trade_date}")
    print(f"ts_code(arg)={ts_code}  start_date={start_date}  end_date={end_date}")
    print(f"offset={offset}  limit={limit}")

    _print_frame(
        "filter_by_trade_date",
        pro.stk_limit(trade_date=trade_date, fields=FIELDS),
    )
    _print_frame(
        "filter_by_ts_code",
        pro.stk_limit(ts_code=ts_code, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_ts_code_and_trade_date",
        pro.stk_limit(ts_code=ts_code, trade_date=trade_date, fields=FIELDS),
    )
    _print_frame(
        "filter_by_start_end_date (single stock)",
        pro.stk_limit(ts_code=ts_code, start_date=start_date, end_date=end_date, fields=FIELDS),
    )
    _print_frame(
        "filter_by_start_end_date (all stocks)",
        pro.stk_limit(start_date=start_date, end_date=end_date, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "limit_only",
        pro.stk_limit(limit=limit, fields=FIELDS),
    )
    _print_frame(
        "offset_and_limit",
        pro.stk_limit(offset=offset, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "no_fields_filter",
        pro.stk_limit(ts_code=ts_code, trade_date=trade_date),
    )
    _print_frame(
        "query_dispatch",
        pro.query("stk_limit", trade_date=trade_date, limit=limit, fields=FIELDS),
    )

    # 涨跌停价格合理性校验：up_limit 应约等于 pre_close * 1.1
    today = pro.stk_limit(trade_date=trade_date, fields=FIELDS)
    if not today.empty:
        today = today.dropna(subset=["pre_close"])
        today["up_ratio"] = (today["up_limit"] / today["pre_close"]).round(4)
        today["down_ratio"] = (today["down_limit"] / today["pre_close"]).round(4)
        up_normal = today[today["up_ratio"].between(1.09, 1.21)]
        down_normal = today[today["down_ratio"].between(0.79, 0.91)]
        print(f"\n## 涨跌停价格合理性 ({trade_date}，共 {len(today)} 只)")
        print(f"  涨停价约为昨收 ×1.1: {len(up_normal)}/{len(today)} 只")
        print(f"  跌停价约为昨收 ×0.9: {len(down_normal)}/{len(today)} 只")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test stk_limit local query parameters against synced Parquet data."
    )
    parser.add_argument("--ts-code", default="000001.SZ")
    parser.add_argument("--trade-date", default="20260605")
    parser.add_argument("--start-date", default="20260501")
    parser.add_argument("--end-date", default="20260605")
    parser.add_argument("--offset", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_smoke(
            ts_code=args.ts_code,
            trade_date=args.trade_date,
            start_date=args.start_date,
            end_date=args.end_date,
            offset=args.offset,
            limit=args.limit,
        )
    except FileNotFoundError as exc:
        print(f"Missing local data: {exc}", file=sys.stderr)
        print("Run: uv run python main.py sync --table stk_limit --start-date 20070104", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid sample query: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
