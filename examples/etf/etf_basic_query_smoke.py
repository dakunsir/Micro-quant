from __future__ import annotations

import argparse
import sys

from zer0share import pro_api


FIELDS = (
    "ts_code,csname,extname,cname,index_code,index_name,"
    "setup_date,list_date,list_status,exchange,mgr_name,custod_name,mgt_fee,etf_type"
)


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def _pick_sample(pro, exchange: str, index_code: str):
    sample = pro.etf_basic(exchange=exchange, index_code=index_code, limit=1, fields=FIELDS)
    if sample.empty:
        raise ValueError(
            "no etf_basic sample found; try different --exchange or --index-code"
        )
    return sample.iloc[0]


def run_smoke(exchange: str, index_code: str, list_status: str, offset: int, limit: int) -> None:
    pro = pro_api()
    sample = _pick_sample(pro, exchange=exchange, index_code=index_code)

    ts_code = sample["ts_code"]
    mgr_name = sample["mgr_name"]
    list_date = sample["list_date"]

    print("Sample values")
    print(f"ts_code={ts_code}")
    print(f"exchange={exchange}")
    print(f"index_code={index_code}")
    print(f"list_status={list_status}")
    print(f"mgr_name={mgr_name}")
    print(f"list_date={list_date}")
    print(f"offset={offset}")
    print(f"limit={limit}")

    _print_frame(
        "filter_by_ts_code",
        pro.etf_basic(ts_code=ts_code, fields=FIELDS),
    )
    _print_frame(
        "filter_by_exchange",
        pro.etf_basic(exchange=exchange, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_index_code",
        pro.etf_basic(index_code=index_code, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_list_status",
        pro.etf_basic(list_status=list_status, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_mgr_name",
        pro.etf_basic(mgr_name=mgr_name, fields=FIELDS),
    )
    _print_frame(
        "filter_by_ts_code_and_exchange",
        pro.etf_basic(ts_code=ts_code, exchange=exchange, fields=FIELDS),
    )
    _print_frame(
        "limit_only",
        pro.etf_basic(exchange=exchange, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "offset_and_limit",
        pro.etf_basic(exchange=exchange, offset=offset, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "no_fields_filter",
        pro.etf_basic(exchange=exchange, index_code=index_code, limit=limit),
    )
    _print_frame(
        "query_dispatch",
        pro.query(
            "etf_basic",
            ts_code=ts_code,
            exchange=exchange,
            index_code=index_code,
            list_status=list_status,
            mgr_name=mgr_name,
            offset=0,
            limit=1,
            fields=FIELDS,
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test etf_basic local query parameters against synced Parquet data."
    )
    parser.add_argument("--exchange", default="SH")
    parser.add_argument("--index-code", default="000300.SH")
    parser.add_argument("--list-status", default="L")
    parser.add_argument("--offset", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_smoke(
            exchange=args.exchange,
            index_code=args.index_code,
            list_status=args.list_status,
            offset=args.offset,
            limit=args.limit,
        )
    except FileNotFoundError as exc:
        print(f"Missing local data: {exc}", file=sys.stderr)
        print("Run the relevant sync command first:", file=sys.stderr)
        print("  uv run python main.py sync --table etf_basic", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid sample query: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
