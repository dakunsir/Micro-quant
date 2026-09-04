from __future__ import annotations

import argparse
import sys

from micro import pro_api

FIELDS = "exchange,cal_date,is_open,pretrade_date"
ALL_EXCHANGES = ["SSE", "SZSE", "CFFEX", "DCE", "SHFE", "CZCE", "INE", "GFEX"]


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def run_smoke(exchange: str, start_date: str, end_date: str,
              offset: int, limit: int) -> None:
    pro = pro_api()

    sample = pro.trade_cal(exchange=exchange, limit=1, fields=FIELDS)
    if sample.empty:
        raise ValueError(
            f"no trade_cal data found for exchange={exchange}; "
            "ensure sync is complete or try a different --exchange"
        )
    cal_date = sample.iloc[0]["cal_date"]

    print("Sample values")
    print(f"exchange={exchange}  cal_date(sample)={cal_date}")
    print(f"start_date={start_date}  end_date={end_date}")
    print(f"offset={offset}  limit={limit}")

    _print_frame(
        "filter_by_exchange",
        pro.trade_cal(exchange=exchange, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_start_end_date",
        pro.trade_cal(exchange=exchange, start_date=start_date, end_date=end_date, fields=FIELDS),
    )
    _print_frame(
        "is_open_true",
        pro.trade_cal(exchange=exchange, start_date=start_date, end_date=end_date,
                      is_open=1, fields=FIELDS),
    )
    _print_frame(
        "is_open_false",
        pro.trade_cal(exchange=exchange, start_date=start_date, end_date=end_date,
                      is_open=0, fields=FIELDS),
    )
    _print_frame(
        "offset_and_limit",
        pro.trade_cal(exchange=exchange, offset=offset, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "no_fields_filter",
        pro.trade_cal(exchange=exchange, start_date=start_date, end_date=end_date),
    )
    _print_frame(
        "query_dispatch",
        pro.query(
            "trade_cal",
            exchange=exchange,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            fields=FIELDS,
        ),
    )

    print("\n## total_open_days_per_exchange")
    for ex in ALL_EXCHANGES:
        df = pro.trade_cal(exchange=ex, is_open=1)
        print(f"  {ex}: {len(df)} trading days")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test trade_cal local query parameters against synced Parquet data."
    )
    parser.add_argument("--exchange", default="SSE")
    parser.add_argument("--start-date", default="20240101")
    parser.add_argument("--end-date", default="20240131")
    parser.add_argument("--offset", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_smoke(
            exchange=args.exchange,
            start_date=args.start_date,
            end_date=args.end_date,
            offset=args.offset,
            limit=args.limit,
        )
    except FileNotFoundError as exc:
        print(f"Missing local data: {exc}", file=sys.stderr)
        print("Run the relevant sync command first:", file=sys.stderr)
        print("  uv run python main.py sync --table trade_cal", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid sample query: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
