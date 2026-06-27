#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from zer0share import pro_api


FIELDS = "trade_date,ts_code,con_code,con_name,qty,sub_flag,cpr,rdr,sca,exchange"


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def _pick_sample(pro):
    sample = pro.etf_sh_cons(limit=1, fields=FIELDS)
    if sample.empty:
        raise ValueError(
            "no etf_sh_cons sample found; run `uv run python main.py sync --table etf_sh_cons` first"
        )
    return sample.iloc[0]


def run_smoke(offset: int, limit: int) -> None:
    pro = pro_api()
    sample = _pick_sample(pro)

    ts_code = sample["ts_code"]
    trade_date = sample["trade_date"]
    con_code = sample["con_code"]

    print("Sample values")
    print(f"ts_code={ts_code}")
    print(f"trade_date={trade_date}")
    print(f"con_code={con_code}")
    print(f"offset={offset}")
    print(f"limit={limit}")

    _print_frame(
        "filter_by_ts_code",
        pro.etf_sh_cons(ts_code=ts_code, fields=FIELDS),
    )
    _print_frame(
        "filter_by_trade_date_and_con_code",
        pro.etf_sh_cons(trade_date=trade_date, con_code=con_code, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "offset_and_limit",
        pro.etf_sh_cons(trade_date=trade_date, offset=offset, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "query_dispatch",
        pro.query("etf_sh_cons", ts_code=ts_code, limit=limit, fields=FIELDS),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test etf_sh_cons local query parameters against synced Parquet data."
    )
    parser.add_argument("--offset", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_smoke(offset=args.offset, limit=args.limit)
    except FileNotFoundError as exc:
        print(f"Missing local data: {exc}", file=sys.stderr)
        print("Run the relevant sync command first:", file=sys.stderr)
        print("  uv run python main.py sync --table etf_sh_cons", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid sample query: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
