from __future__ import annotations

import argparse
import sys

from micro import pro_api


FIELDS = "ts_code,trade_date,freq,open,high,low,close,settle,vol,amount,oi,exchange"


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def _pick_sample(pro, fn_name: str, ts_code: str):
    df = getattr(pro, fn_name)(ts_code=ts_code, limit=1, fields=FIELDS)
    if df.empty:
        raise ValueError(
            f"no {fn_name} data found for {ts_code}; "
            "ensure sync is complete or try a different --ts-code"
        )
    return df.iloc[0]


def run_smoke(fn_name: str, ts_code: str, trade_date: str,
              start_date: str, end_date: str, exchange: str,
              offset: int, limit: int) -> None:
    pro = pro_api()
    fn = getattr(pro, fn_name)
    sample = _pick_sample(pro, fn_name, ts_code=ts_code)

    actual_trade_date = sample["trade_date"]

    print(f"=== {fn_name} ===")
    print(f"ts_code={ts_code}  trade_date(sample)={actual_trade_date}")
    print(f"trade_date(arg)={trade_date}  start_date={start_date}  end_date={end_date}")
    print(f"exchange={exchange}  offset={offset}  limit={limit}")

    _print_frame(
        "filter_by_ts_code",
        fn(ts_code=ts_code, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_trade_date",
        fn(trade_date=actual_trade_date, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_ts_code_and_trade_date",
        fn(ts_code=ts_code, trade_date=actual_trade_date, fields=FIELDS),
    )
    _print_frame(
        "filter_by_start_end_date",
        fn(ts_code=ts_code, start_date=start_date, end_date=end_date, fields=FIELDS),
    )
    _print_frame(
        "filter_by_exchange",
        fn(exchange=exchange, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_ts_code_multi",
        fn(ts_code="CU.SHF,AL.SHF", start_date=start_date, end_date=end_date, fields=FIELDS),
    )
    _print_frame(
        "limit_only",
        fn(limit=limit, fields=FIELDS),
    )
    _print_frame(
        "offset_and_limit",
        fn(offset=offset, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "no_fields_filter",
        fn(ts_code=ts_code, trade_date=actual_trade_date),
    )
    _print_frame(
        "query_dispatch",
        pro.query(
            fn_name,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            offset=0,
            limit=1,
            fields=FIELDS,
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test fut_weekly / fut_monthly local query parameters."
    )
    parser.add_argument("--table", choices=["fut_weekly", "fut_monthly"], default="fut_weekly")
    parser.add_argument("--ts-code", default="CU.SHF")
    parser.add_argument("--trade-date", default="19950421")
    parser.add_argument("--start-date", default="19950417")
    parser.add_argument("--end-date", default="19951231")
    parser.add_argument("--exchange", default="SHFE")
    parser.add_argument("--offset", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_smoke(
            fn_name=args.table,
            ts_code=args.ts_code,
            trade_date=args.trade_date,
            start_date=args.start_date,
            end_date=args.end_date,
            exchange=args.exchange,
            offset=args.offset,
            limit=args.limit,
        )
    except FileNotFoundError as exc:
        print(f"Missing local data: {exc}", file=sys.stderr)
        print("Run the relevant sync command first:", file=sys.stderr)
        print(f"  uv run python main.py sync --table {args.table}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid sample query: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
