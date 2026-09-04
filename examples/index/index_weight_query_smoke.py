from __future__ import annotations

import argparse
import sys

from microshare import pro_api


FIELDS = "index_code,con_code,trade_date,weight"


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def _pick_sample(pro, index_code: str):
    sample = pro.index_weight(index_code=index_code, limit=1, fields=FIELDS)
    if sample.empty:
        raise ValueError(
            f"no index_weight data found for index_code={index_code}; "
            "ensure sync is complete or try a different --index-code"
        )
    return sample.iloc[0]


def run_smoke(index_code: str, start_date: str, end_date: str,
              offset: int, limit: int) -> None:
    pro = pro_api()
    sample = _pick_sample(pro, index_code=index_code)

    trade_date = sample["trade_date"]
    con_code = sample["con_code"]

    print("Sample values")
    print(f"index_code={index_code}  trade_date(sample)={trade_date}  con_code(sample)={con_code}")
    print(f"start_date={start_date}  end_date={end_date}")
    print(f"offset={offset}  limit={limit}")

    _print_frame(
        "filter_by_index_code",
        pro.index_weight(index_code=index_code, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_trade_date",
        pro.index_weight(trade_date=trade_date, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_index_code_and_trade_date",
        pro.index_weight(index_code=index_code, trade_date=trade_date, fields=FIELDS),
    )
    _print_frame(
        "filter_by_start_end_date",
        pro.index_weight(index_code=index_code, start_date=start_date, end_date=end_date, fields=FIELDS),
    )
    _print_frame(
        "all_indices_on_trade_date",
        pro.index_weight(trade_date=trade_date, fields=FIELDS),
    )
    _print_frame(
        "limit_only",
        pro.index_weight(limit=limit, fields=FIELDS),
    )
    _print_frame(
        "offset_and_limit",
        pro.index_weight(offset=offset, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "no_fields_filter",
        pro.index_weight(index_code=index_code, trade_date=trade_date),
    )
    _print_frame(
        "query_dispatch",
        pro.query(
            "index_weight",
            index_code=index_code,
            start_date=start_date,
            end_date=end_date,
            offset=0,
            limit=1,
            fields=FIELDS,
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test index_weight local query parameters against synced Parquet data."
    )
    parser.add_argument("--index-code", default="399300.SZ")
    parser.add_argument("--start-date", default="20160101")
    parser.add_argument("--end-date", default="20160331")
    parser.add_argument("--offset", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_smoke(
            index_code=args.index_code,
            start_date=args.start_date,
            end_date=args.end_date,
            offset=args.offset,
            limit=args.limit,
        )
    except FileNotFoundError as exc:
        print(f"Missing local data: {exc}", file=sys.stderr)
        print("Run the relevant sync command first:", file=sys.stderr)
        print("  uv run python main.py sync --table index_weight", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid sample query: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
