from __future__ import annotations

import argparse
import sys

from micro import pro_api


FIELDS = (
    "ts_code,exchange,opt_code,call_put,name,list_date,"
    "maturity_date,last_edate,last_ddate"
)


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def _pick_sample(pro, exchange: str, opt_code: str, call_put: str):
    sample = pro.opt_basic(
        exchange=exchange,
        opt_code=opt_code,
        call_put=call_put,
        limit=1,
        fields=FIELDS,
    )
    if sample.empty:
        raise ValueError(
            "no opt_basic sample found; try different --exchange, --opt-code, or --call-put"
        )
    return sample.iloc[0]


def run_smoke(exchange: str, opt_code: str, call_put: str, offset: int, limit: int) -> None:
    pro = pro_api()
    sample = _pick_sample(pro, exchange=exchange, opt_code=opt_code, call_put=call_put)

    ts_code = sample["ts_code"]
    name = sample["name"]
    list_date = sample["list_date"]

    print("Sample values")
    print(f"ts_code={ts_code}")
    print(f"exchange={exchange}")
    print(f"opt_code={opt_code}")
    print(f"call_put={call_put}")
    print(f"name={name}")
    print(f"list_date={list_date}")
    print(f"offset={offset}")
    print(f"limit={limit}")

    _print_frame(
        "filter_by_ts_code",
        pro.opt_basic(ts_code=ts_code, fields=FIELDS),
    )
    _print_frame(
        "filter_by_exchange",
        pro.opt_basic(exchange=exchange, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_opt_code",
        pro.opt_basic(opt_code=opt_code, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_call_put",
        pro.opt_basic(call_put=call_put, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_name",
        pro.opt_basic(name=name, fields=FIELDS),
    )
    _print_frame(
        "filter_by_list_date",
        pro.opt_basic(list_date=list_date, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "limit_only",
        pro.opt_basic(exchange=exchange, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "offset_and_limit",
        pro.opt_basic(exchange=exchange, offset=offset, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "query_dispatch_all_params",
        pro.query(
            "opt_basic",
            ts_code=ts_code,
            exchange=exchange,
            opt_code=opt_code,
            call_put=call_put,
            name=name,
            list_date=list_date,
            offset=0,
            limit=1,
            fields=FIELDS,
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test opt_basic local query parameters against synced Parquet data."
    )
    parser.add_argument("--exchange", default="SSE")
    parser.add_argument("--opt-code", default="OP510050.SH")
    parser.add_argument("--call-put", default="C")
    parser.add_argument("--offset", type=int, default=1)
    parser.add_argument("--limit", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_smoke(
            exchange=args.exchange,
            opt_code=args.opt_code,
            call_put=args.call_put,
            offset=args.offset,
            limit=args.limit,
        )
    except FileNotFoundError as exc:
        print(f"Missing local data: {exc}", file=sys.stderr)
        print("Run the relevant sync command first:", file=sys.stderr)
        print("  uv run python main.py sync --table opt_basic", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid sample query: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
