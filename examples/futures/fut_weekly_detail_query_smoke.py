from __future__ import annotations

import argparse
import sys

from microshare import pro_api


FIELDS = "week_date,week,exchange,prd,name,vol,vol_yoy,amount,amout_yoy,cumvol,cumvol_yoy,cumamt,cumamt_yoy,open_interest,interest_wow,mc_close,close_wow"


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def _pick_sample(pro, exchange: str):
    sample = pro.fut_weekly_detail(exchange=exchange, limit=1, fields="week_date,week,exchange,prd,name")
    if sample.empty:
        raise ValueError(
            f"no fut_weekly_detail data found for exchange={exchange}; "
            "ensure sync is complete or try a different --exchange"
        )
    return sample.iloc[0]


def run_smoke(exchange: str, prd: str, start_date: str, end_date: str,
              offset: int, limit: int) -> None:
    pro = pro_api()
    sample = _pick_sample(pro, exchange=exchange)

    week_date = sample["week_date"]
    week = sample["week"]

    print("Sample values")
    print(f"exchange={exchange}  prd={prd}  week_date(sample)={week_date}  week(sample)={week}")
    print(f"start_date={start_date}  end_date={end_date}")
    print(f"offset={offset}  limit={limit}")

    _print_frame(
        "filter_by_exchange",
        pro.fut_weekly_detail(exchange=exchange, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_prd",
        pro.fut_weekly_detail(prd=prd, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_exchange_and_prd",
        pro.fut_weekly_detail(exchange=exchange, prd=prd, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_start_end_date",
        pro.fut_weekly_detail(exchange=exchange, start_date=start_date, end_date=end_date, fields=FIELDS),
    )
    _print_frame(
        "limit_only",
        pro.fut_weekly_detail(limit=limit, fields=FIELDS),
    )
    _print_frame(
        "offset_and_limit",
        pro.fut_weekly_detail(offset=offset, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "no_fields_filter",
        pro.fut_weekly_detail(exchange=exchange, prd=prd, limit=limit),
    )
    _print_frame(
        "query_dispatch",
        pro.query(
            "fut_weekly_detail",
            exchange=exchange,
            start_date=start_date,
            end_date=end_date,
            offset=0,
            limit=1,
            fields=FIELDS,
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test fut_weekly_detail local query parameters against synced Parquet data."
    )
    parser.add_argument("--exchange", default="SHFE")
    parser.add_argument("--prd", default="CU")
    parser.add_argument("--start-date", default="20160101")
    parser.add_argument("--end-date", default="20160331")
    parser.add_argument("--offset", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_smoke(
            exchange=args.exchange,
            prd=args.prd,
            start_date=args.start_date,
            end_date=args.end_date,
            offset=args.offset,
            limit=args.limit,
        )
    except FileNotFoundError as exc:
        print(f"Missing local data: {exc}", file=sys.stderr)
        print("Run the relevant sync command first:", file=sys.stderr)
        print("  uv run python main.py sync --table fut_weekly_detail", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid sample query: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
