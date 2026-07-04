from __future__ import annotations

import argparse
import sys

from zer0share import pro_api


FIELDS = "trade_date,ts_code,etf_name,total_share,total_size,nav,close,exchange"


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def _pick_sample(pro, trade_date: str):
    sample = pro.etf_share_size(trade_date=trade_date, limit=1, fields=FIELDS)
    if sample.empty:
        raise ValueError(
            "no etf_share_size sample found; try a different --trade-date or run `uv run python main.py sync --table etf_share_size` first"
        )
    return sample.iloc[0]


def run_smoke(trade_date: str, offset: int, limit: int) -> None:
    pro = pro_api()
    sample = _pick_sample(pro, trade_date=trade_date)

    ts_code = sample["ts_code"]
    sample_trade_date = sample["trade_date"]
    exchange = sample["exchange"]

    print("Sample values")
    print(f"ts_code={ts_code}")
    print(f"trade_date={sample_trade_date}")
    print(f"exchange={exchange}")
    print(f"offset={offset}")
    print(f"limit={limit}")

    _print_frame(
        "filter_by_ts_code",
        pro.etf_share_size(ts_code=ts_code, trade_date=sample_trade_date, fields=FIELDS),
    )
    _print_frame(
        "filter_by_trade_date_and_exchange",
        pro.etf_share_size(trade_date=sample_trade_date, exchange=exchange, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "offset_and_limit",
        pro.etf_share_size(trade_date=sample_trade_date, offset=offset, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "query_dispatch",
        pro.query("etf_share_size", ts_code=ts_code, trade_date=sample_trade_date, limit=limit, fields=FIELDS),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test etf_share_size local query parameters against synced Parquet data."
    )
    parser.add_argument("--trade-date", default="20260703")
    parser.add_argument("--offset", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_smoke(trade_date=args.trade_date, offset=args.offset, limit=args.limit)
    except FileNotFoundError as exc:
        print(f"Missing local data: {exc}", file=sys.stderr)
        print("Run the relevant sync command first:", file=sys.stderr)
        print("  uv run python main.py sync --table etf_share_size", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid sample query: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
