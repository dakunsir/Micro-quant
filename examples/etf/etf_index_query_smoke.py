from __future__ import annotations

import argparse
import sys

from zer0share import pro_api


FIELDS = "ts_code,indx_name,indx_csname,pub_party_name,pub_date,base_date,bp,adj_circle"


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def _pick_sample(pro, ts_code: str):
    sample = pro.etf_index(ts_code=ts_code, limit=1, fields=FIELDS)
    if sample.empty:
        raise ValueError("no etf_index sample found; try different --ts-code")
    return sample.iloc[0]


def run_smoke(ts_code: str, offset: int, limit: int) -> None:
    pro = pro_api()
    sample = _pick_sample(pro, ts_code=ts_code)

    pub_date = sample["pub_date"]
    base_date = sample["base_date"]

    print("Sample values")
    print(f"ts_code={ts_code}")
    print(f"pub_date={pub_date}")
    print(f"base_date={base_date}")
    print(f"offset={offset}")
    print(f"limit={limit}")

    _print_frame("filter_by_ts_code", pro.etf_index(ts_code=ts_code, fields=FIELDS))
    _print_frame("filter_by_pub_date", pro.etf_index(pub_date=pub_date, limit=limit, fields=FIELDS))
    _print_frame("filter_by_base_date", pro.etf_index(base_date=base_date, limit=limit, fields=FIELDS))
    _print_frame("limit_only", pro.etf_index(limit=limit, fields=FIELDS))
    _print_frame("offset_and_limit", pro.etf_index(offset=offset, limit=limit, fields=FIELDS))
    _print_frame("no_fields_filter", pro.etf_index(ts_code=ts_code, limit=limit))
    _print_frame(
        "query_dispatch",
        pro.query(
            "etf_index",
            ts_code=ts_code,
            pub_date=pub_date,
            base_date=base_date,
            offset=0,
            limit=1,
            fields=FIELDS,
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test etf_index local query parameters against synced Parquet data."
    )
    parser.add_argument("--ts-code", default="000300.SH")
    parser.add_argument("--offset", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_smoke(ts_code=args.ts_code, offset=args.offset, limit=args.limit)
    except FileNotFoundError as exc:
        print(f"Missing local data: {exc}", file=sys.stderr)
        print("Run the relevant sync command first:", file=sys.stderr)
        print("  uv run python main.py sync --table etf_index", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid sample query: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
