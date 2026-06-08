from __future__ import annotations

import argparse
import sys

from zer0share import pro_api


FIELDS = "ts_code,name,trade_date,type,type_name"


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def _pick_sample(pro, trade_date: str):
    sample = pro.stock_st(trade_date=trade_date, limit=1, fields=FIELDS)
    if sample.empty:
        raise ValueError(
            f"no stock_st data found for trade_date={trade_date}; "
            "data starts around 2016-12 — try a more recent date"
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
        pro.stock_st(trade_date=trade_date, fields=FIELDS),
    )
    _print_frame(
        "filter_by_ts_code",
        pro.stock_st(ts_code=ts_code_sample, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_ts_code_and_trade_date",
        pro.stock_st(ts_code=ts_code_sample, trade_date=trade_date, fields=FIELDS),
    )
    _print_frame(
        "filter_by_start_end_date (single stock)",
        pro.stock_st(ts_code=ts_code_sample, start_date=start_date, end_date=end_date, fields=FIELDS),
    )
    _print_frame(
        "filter_by_start_end_date (all stocks)",
        pro.stock_st(start_date=start_date, end_date=end_date, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "limit_only",
        pro.stock_st(limit=limit, fields=FIELDS),
    )
    _print_frame(
        "offset_and_limit",
        pro.stock_st(offset=offset, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "no_fields_filter",
        pro.stock_st(ts_code=ts_code_sample, trade_date=trade_date),
    )
    _print_frame(
        "query_dispatch",
        pro.query("stock_st", trade_date=trade_date, limit=limit, fields=FIELDS),
    )

    # ST 类型分布汇总
    all_today = pro.stock_st(trade_date=trade_date, fields=FIELDS)
    if not all_today.empty:
        print(f"\n## ST类型分布 ({trade_date})")
        print(all_today.groupby("type_name").size().rename("count").to_string())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test stock_st local query parameters against synced Parquet data."
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
        print("Run: uv run python main.py sync --table stock_st --start-date 20160101", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid sample query: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
