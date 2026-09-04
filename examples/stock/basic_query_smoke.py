from __future__ import annotations

import argparse
import sys

from microshare import pro_api


FIELDS = "ts_code,symbol,name,area,industry,market,exchange,list_status,list_date,delist_date,is_hs"


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def run_smoke(ts_code: str, name: str, market: str, exchange: str,
              list_status: str, is_hs: str, offset: int, limit: int) -> None:
    pro = pro_api()

    print("Sample values")
    print(f"ts_code={ts_code}  name={name}  market={market}")
    print(f"exchange={exchange}  list_status={list_status}  is_hs={is_hs}")
    print(f"offset={offset}  limit={limit}")

    _print_frame(
        "filter_by_ts_code",
        pro.stock_basic(ts_code=ts_code, fields=FIELDS),
    )
    _print_frame(
        "filter_by_name",
        pro.stock_basic(name=name, fields=FIELDS),
    )
    _print_frame(
        "filter_by_market",
        pro.stock_basic(market=market, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_exchange",
        pro.stock_basic(exchange=exchange, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_list_status_L",
        pro.stock_basic(list_status="L", limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_list_status_D",
        pro.stock_basic(list_status="D", limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_is_hs",
        pro.stock_basic(is_hs=is_hs, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "limit_only",
        pro.stock_basic(limit=limit, fields=FIELDS),
    )
    _print_frame(
        "offset_and_limit",
        pro.stock_basic(offset=offset, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "no_fields_filter",
        pro.stock_basic(ts_code=ts_code),
    )
    _print_frame(
        "query_dispatch",
        pro.query("stock_basic", ts_code=ts_code, fields=FIELDS),
    )

    # 汇总统计
    all_df = pro.stock_basic(fields="ts_code,exchange,list_status")
    print(f"\n## summary")
    print(f"total stocks: {len(all_df)}")
    print(all_df.groupby(["exchange", "list_status"]).size().rename("count").to_string())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test stock_basic local query parameters against synced Parquet data."
    )
    parser.add_argument("--ts-code", default="000001.SZ")
    parser.add_argument("--name", default="平安银行")
    parser.add_argument("--market", default="主板")
    parser.add_argument("--exchange", default="SZSE")
    parser.add_argument("--list-status", default="L")
    parser.add_argument("--is-hs", default="S")
    parser.add_argument("--offset", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_smoke(
            ts_code=args.ts_code,
            name=args.name,
            market=args.market,
            exchange=args.exchange,
            list_status=args.list_status,
            is_hs=args.is_hs,
            offset=args.offset,
            limit=args.limit,
        )
    except FileNotFoundError as exc:
        print(f"Missing local data: {exc}", file=sys.stderr)
        print("Run the relevant sync command first:", file=sys.stderr)
        print("  uv run python main.py sync --table basic", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
