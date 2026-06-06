from __future__ import annotations

import argparse
import sys

from zer0share import pro_api


FIELDS = (
    "ts_code,trade_date,exchange,open,high,low,close,settle,vol,amount,oi"
)


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def _pick_sample(pro, trade_date: str, exchange: str | None):
    sample = pro.opt_daily(
        trade_date=trade_date,
        exchange=exchange,
        limit=1,
        fields=FIELDS,
    )
    if sample.empty:
        detail = f"trade_date={trade_date}"
        if exchange is not None:
            detail += f", exchange={exchange}"
        raise ValueError(f"no opt_daily sample found for {detail}")
    return sample.iloc[0]


def run_smoke(
    trade_date: str,
    start_date: str,
    end_date: str,
    exchange: str | None,
    ts_code: str | None,
    offset: int,
    limit: int,
) -> None:
    pro = pro_api()
    sample = _pick_sample(pro, trade_date=trade_date, exchange=exchange)
    sample_ts_code = ts_code or sample["ts_code"]
    sample_exchange = exchange or sample["exchange"]

    print("Sample values")
    print(f"ts_code={sample_ts_code}")
    print(f"trade_date={trade_date}")
    print(f"start_date={start_date}")
    print(f"end_date={end_date}")
    print(f"exchange={sample_exchange}")
    print(f"offset={offset}")
    print(f"limit={limit}")

    _print_frame(
        "filter_by_trade_date",
        pro.opt_daily(trade_date=trade_date, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_trade_date_and_exchange",
        pro.opt_daily(
            trade_date=trade_date,
            exchange=sample_exchange,
            limit=limit,
            fields=FIELDS,
        ),
    )
    _print_frame(
        "filter_by_ts_code_and_trade_date",
        pro.opt_daily(
            ts_code=sample_ts_code,
            trade_date=trade_date,
            fields=FIELDS,
        ),
    )
    _print_frame(
        "filter_by_date_range",
        pro.opt_daily(
            start_date=start_date,
            end_date=end_date,
            exchange=sample_exchange,
            limit=limit,
            fields=FIELDS,
        ),
    )
    _print_frame(
        "offset_and_limit",
        pro.opt_daily(
            trade_date=trade_date,
            exchange=sample_exchange,
            offset=offset,
            limit=limit,
            fields=FIELDS,
        ),
    )
    _print_frame(
        "query_dispatch",
        pro.query(
            "opt_daily",
            ts_code=sample_ts_code,
            start_date=start_date,
            end_date=end_date,
            exchange=sample_exchange,
            limit=limit,
            fields=FIELDS,
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test opt_daily local queries against synced Parquet data."
    )
    parser.add_argument("--trade-date", default="20150209")
    parser.add_argument("--start-date", default="20150209")
    parser.add_argument("--end-date", default="20150213")
    parser.add_argument("--exchange", default="SSE")
    parser.add_argument("--ts-code", default=None)
    parser.add_argument("--offset", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_smoke(
            trade_date=args.trade_date,
            start_date=args.start_date,
            end_date=args.end_date,
            exchange=args.exchange,
            ts_code=args.ts_code,
            offset=args.offset,
            limit=args.limit,
        )
    except FileNotFoundError as exc:
        print(f"Missing local data: {exc}", file=sys.stderr)
        print("Run the relevant sync command first:", file=sys.stderr)
        print(
            "  uv run python main.py sync --table opt_daily "
            "--start-date 20150209 --end-date 20150213",
            file=sys.stderr,
        )
        return 1
    except ValueError as exc:
        print(f"Invalid sample query: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
