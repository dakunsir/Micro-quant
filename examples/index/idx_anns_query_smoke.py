from __future__ import annotations

import argparse
import sys

from microshare import pro_api


FIELDS = "ann_date,title,source,type"


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def _pick_sample(pro, start_date: str, end_date: str):
    sample = pro.idx_anns(start_date=start_date, end_date=end_date, limit=1, fields=FIELDS)
    if sample.empty:
        raise ValueError(
            "no idx_anns data found for the requested range; "
            "ensure sync is complete or try a different --start-date/--end-date"
        )
    return sample.iloc[0]


def run_smoke(start_date: str, end_date: str, offset: int, limit: int) -> None:
    pro = pro_api()
    sample = _pick_sample(pro, start_date=start_date, end_date=end_date)

    ann_date = sample["ann_date"]
    source = sample["source"]

    print("Sample values")
    print(f"ann_date(sample)={ann_date}  source(sample)={source}")
    print(f"start_date={start_date}  end_date={end_date}")
    print(f"offset={offset}  limit={limit}")

    _print_frame(
        "filter_by_ann_date",
        pro.idx_anns(ann_date=ann_date, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_source",
        pro.idx_anns(src=source, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_ann_date_and_source",
        pro.idx_anns(ann_date=ann_date, src=source, fields=FIELDS),
    )
    _print_frame(
        "filter_by_start_end_date",
        pro.idx_anns(start_date=start_date, end_date=end_date, fields=FIELDS),
    )
    _print_frame(
        "limit_only",
        pro.idx_anns(limit=limit, fields=FIELDS),
    )
    _print_frame(
        "offset_and_limit",
        pro.idx_anns(offset=offset, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "no_fields_filter",
        pro.idx_anns(ann_date=ann_date),
    )
    _print_frame(
        "query_dispatch",
        pro.query(
            "idx_anns",
            start_date=start_date,
            end_date=end_date,
            offset=0,
            limit=1,
            fields=FIELDS,
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test idx_anns local query parameters against synced Parquet data."
    )
    parser.add_argument("--start-date", default="20260401")
    parser.add_argument("--end-date", default="20260430")
    parser.add_argument("--offset", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_smoke(
            start_date=args.start_date,
            end_date=args.end_date,
            offset=args.offset,
            limit=args.limit,
        )
    except FileNotFoundError as exc:
        print(f"Missing local data: {exc}", file=sys.stderr)
        print("Run the relevant sync command first:", file=sys.stderr)
        print("  uv run python main.py sync --table idx_anns", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid sample query: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
