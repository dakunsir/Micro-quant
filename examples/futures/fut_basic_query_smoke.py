from __future__ import annotations

import argparse
import sys

from micro import pro_api


FIELDS = "ts_code,symbol,exchange,name,fut_code,multiplier,list_date,delist_date,last_ddate"


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def _pick_sample(pro, exchange: str, fut_code: str):
    sample = pro.fut_basic(exchange=exchange, fut_code=fut_code, limit=1, fields=FIELDS)
    if sample.empty:
        raise ValueError(
            "no fut_basic sample found; try different --exchange or --fut-code"
        )
    return sample.iloc[0]


def run_smoke(exchange: str, fut_code: str, offset: int, limit: int) -> None:
    pro = pro_api()
    sample = _pick_sample(pro, exchange=exchange, fut_code=fut_code)

    ts_code = sample["ts_code"]
    name = sample["name"]

    print("Sample values")
    print(f"ts_code={ts_code}")
    print(f"exchange={exchange}")
    print(f"fut_code={fut_code}")
    print(f"name={name}")
    print(f"offset={offset}")
    print(f"limit={limit}")

    _print_frame(
        "filter_by_ts_code",
        pro.fut_basic(ts_code=ts_code, fields=FIELDS),
    )
    _print_frame(
        "filter_by_exchange",
        pro.fut_basic(exchange=exchange, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_fut_code",
        pro.fut_basic(fut_code=fut_code, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_ts_code_multi",
        pro.fut_basic(ts_code="IC1506.CFX,IC1507.CFX", fields=FIELDS),
    )
    _print_frame(
        "limit_only",
        pro.fut_basic(limit=limit, fields=FIELDS),
    )
    _print_frame(
        "offset_and_limit",
        pro.fut_basic(offset=offset, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "no_fields_filter",
        pro.fut_basic(exchange=exchange, fut_code=fut_code, limit=limit),
    )
    _print_frame(
        "query_dispatch",
        pro.query(
            "fut_basic",
            ts_code=ts_code,
            exchange=exchange,
            fut_code=fut_code,
            offset=0,
            limit=1,
            fields=FIELDS,
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test fut_basic local query parameters against synced Parquet data."
    )
    parser.add_argument("--exchange", default="CFFEX")
    parser.add_argument("--fut-code", default="IC")
    parser.add_argument("--offset", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_smoke(
            exchange=args.exchange,
            fut_code=args.fut_code,
            offset=args.offset,
            limit=args.limit,
        )
    except FileNotFoundError as exc:
        print(f"Missing local data: {exc}", file=sys.stderr)
        print("Run the relevant sync command first:", file=sys.stderr)
        print("  uv run python main.py sync --table fut_basic", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid sample query: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
