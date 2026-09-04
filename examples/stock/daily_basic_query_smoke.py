from __future__ import annotations

import argparse
import sys

from microshare import pro_api


FIELDS = (
    "ts_code,trade_date,close,turnover_rate,turnover_rate_f,volume_ratio,"
    "pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,"
    "total_share,float_share,free_share,total_mv,circ_mv,limit_status"
)


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def _pick_sample(pro, ts_code: str, start_date: str, end_date: str):
    sample = pro.daily_basic(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        limit=1,
        fields=FIELDS,
    )
    if sample.empty:
        raise ValueError(
            f"no daily_basic data found for ts_code={ts_code}; "
            "ensure sync is complete or try a different --ts-code"
        )
    return sample.iloc[0]


def run_smoke(ts_code: str, start_date: str, end_date: str,
              offset: int, limit: int) -> None:
    pro = pro_api()
    sample = _pick_sample(
        pro,
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
    )
    trade_date = sample["trade_date"]

    print("Sample values")
    print(f"ts_code={ts_code}  trade_date(sample)={trade_date}")
    print(f"start_date={start_date}  end_date={end_date}")
    print(f"offset={offset}  limit={limit}")

    _print_frame(
        "filter_by_ts_code",
        pro.daily_basic(
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            fields=FIELDS,
        ),
    )
    _print_frame(
        "filter_by_trade_date",
        pro.daily_basic(trade_date=trade_date, fields=FIELDS),
    )
    _print_frame(
        "filter_by_ts_code_and_trade_date",
        pro.daily_basic(ts_code=ts_code, trade_date=trade_date, fields=FIELDS),
    )
    _print_frame(
        "filter_by_start_end_date",
        pro.daily_basic(ts_code=ts_code, start_date=start_date, end_date=end_date, fields=FIELDS),
    )
    _print_frame(
        "all_stocks_on_trade_date",
        pro.daily_basic(trade_date=trade_date, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "limit_only",
        pro.daily_basic(start_date=start_date, end_date=end_date, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "offset_and_limit",
        pro.daily_basic(
            start_date=start_date,
            end_date=end_date,
            offset=offset,
            limit=limit,
            fields=FIELDS,
        ),
    )
    _print_frame(
        "no_fields_filter",
        pro.daily_basic(ts_code=ts_code, trade_date=trade_date),
    )
    _print_frame(
        "query_dispatch",
        pro.query(
            "daily_basic",
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date,
            offset=0,
            limit=1,
            fields=FIELDS,
        ),
    )

    # limit_status 分布汇总
    today = pro.daily_basic(trade_date=trade_date, fields="ts_code,trade_date,limit_status")
    if not today.empty and "limit_status" in today.columns:
        mapping = {1: "涨停", -1: "跌停", 0: "正常"}
        dist = today["limit_status"].map(mapping).value_counts()
        print(f"\n## limit_status 分布 ({trade_date})")
        print(dist.to_string())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test daily_basic local query parameters against synced Parquet data."
    )
    parser.add_argument("--ts-code", default="000001.SZ")
    parser.add_argument("--start-date", default="19901219")
    parser.add_argument("--end-date", default="19911231")
    parser.add_argument("--offset", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_smoke(
            ts_code=args.ts_code,
            start_date=args.start_date,
            end_date=args.end_date,
            offset=args.offset,
            limit=args.limit,
        )
    except FileNotFoundError as exc:
        print(f"Missing local data: {exc}", file=sys.stderr)
        print("Run: uv run python main.py sync --table daily_basic --start-date 19901219", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid sample query: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
