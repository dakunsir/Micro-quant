from __future__ import annotations

import argparse
import sys

from microshare import pro_api


FIELDS = "trade_date,ts_code,name,up_limit,down_limit,m_ratio,cont,exchange"


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def _pick_sample(pro, ts_code: str):
    sample = pro.ft_limit(ts_code=ts_code, limit=1, fields=FIELDS)
    if sample.empty:
        raise ValueError(
            f"no ft_limit data found for ts_code={ts_code}; "
            "ensure sync is complete or try a different --ts-code"
        )
    return sample.iloc[0]


def run_smoke(ts_code: str, exchange: str, start_date: str, end_date: str,
              offset: int, limit: int) -> None:
    pro = pro_api()
    sample = _pick_sample(pro, ts_code=ts_code)

    trade_date = sample["trade_date"]

    print("Sample values")
    print(f"ts_code={ts_code}  trade_date(sample)={trade_date}")
    print(f"exchange={exchange}  start_date={start_date}  end_date={end_date}")
    print(f"offset={offset}  limit={limit}")

    _print_frame(
        "filter_by_ts_code",
        pro.ft_limit(ts_code=ts_code, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_trade_date",
        pro.ft_limit(trade_date=trade_date, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_ts_code_and_trade_date",
        pro.ft_limit(ts_code=ts_code, trade_date=trade_date, fields=FIELDS),
    )
    _print_frame(
        "filter_by_start_end_date",
        pro.ft_limit(ts_code=ts_code, start_date=start_date, end_date=end_date, fields=FIELDS),
    )
    _print_frame(
        "filter_by_exchange",
        pro.ft_limit(exchange=exchange, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "limit_only",
        pro.ft_limit(limit=limit, fields=FIELDS),
    )
    _print_frame(
        "offset_and_limit",
        pro.ft_limit(offset=offset, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "no_fields_filter",
        pro.ft_limit(ts_code=ts_code, trade_date=trade_date),
    )
    _print_frame(
        "query_dispatch",
        pro.query(
            "ft_limit",
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            offset=0,
            limit=1,
            fields=FIELDS,
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test ft_limit local query parameters against synced Parquet data."
    )
    parser.add_argument("--ts-code", default="CU0502.SHF")
    parser.add_argument("--exchange", default="SHFE")
    parser.add_argument("--start-date", default="20050104")
    parser.add_argument("--end-date", default="20050131")
    parser.add_argument("--offset", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_smoke(
            ts_code=args.ts_code,
            exchange=args.exchange,
            start_date=args.start_date,
            end_date=args.end_date,
            offset=args.offset,
            limit=args.limit,
        )
    except FileNotFoundError as exc:
        print(f"Missing local data: {exc}", file=sys.stderr)
        print("Run the relevant sync command first:", file=sys.stderr)
        print("  uv run python main.py sync --table ft_limit", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid sample query: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
