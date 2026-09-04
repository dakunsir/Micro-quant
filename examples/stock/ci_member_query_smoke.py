from __future__ import annotations

import argparse
import sys

from microshare import pro_api


FIELDS = "l1_code,l1_name,l2_code,l2_name,l3_code,l3_name,ts_code,name,in_date,out_date,is_new"


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def run_smoke(ts_code: str, l1_code: str, l2_code: str, l3_code: str,
              is_new: str, limit: int, offset: int) -> None:
    pro = pro_api()

    print("Sample values")
    print(f"ts_code={ts_code}  l1_code={l1_code}  l2_code={l2_code}")
    print(f"l3_code={l3_code}  is_new={is_new}  limit={limit}  offset={offset}")

    _print_frame(
        "filter_by_ts_code",
        pro.ci_index_member(ts_code=ts_code, fields=FIELDS),
    )
    _print_frame(
        "filter_by_l1_code",
        pro.ci_index_member(l1_code=l1_code, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_l2_code",
        pro.ci_index_member(l2_code=l2_code, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_l3_code",
        pro.ci_index_member(l3_code=l3_code, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_is_new",
        pro.ci_index_member(is_new=is_new, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "filter_by_ts_code_and_is_new",
        pro.ci_index_member(ts_code=ts_code, is_new=is_new, fields=FIELDS),
    )
    _print_frame(
        "limit_only",
        pro.ci_index_member(limit=limit, fields=FIELDS),
    )
    _print_frame(
        "offset_and_limit",
        pro.ci_index_member(offset=offset, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "no_fields_filter",
        pro.ci_index_member(ts_code=ts_code),
    )
    _print_frame(
        "query_dispatch",
        pro.query("ci_member", ts_code=ts_code, limit=limit, fields=FIELDS),
    )

    # 中信一级行业成员分布（最新）
    new_df = pro.ci_index_member(is_new="Y", fields="l1_code,l1_name,ts_code")
    if not new_df.empty:
        dist = new_df.groupby(["l1_code", "l1_name"])["ts_code"].count().rename("股票数")
        print(f"\n## 中信一级行业成员分布（is_new=Y，共 {len(new_df)} 只）")
        print(dist.sort_values(ascending=False).head(10).to_string())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test ci_member local query parameters against synced Parquet data."
    )
    parser.add_argument("--ts-code", default="000001.SZ")
    parser.add_argument("--l1-code", default="CI005021.CI")
    parser.add_argument("--l2-code", default="CI005164.CI")
    parser.add_argument("--l3-code", default="CI005343.CI")
    parser.add_argument("--is-new", default="Y")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--offset", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_smoke(
            ts_code=args.ts_code,
            l1_code=args.l1_code,
            l2_code=args.l2_code,
            l3_code=args.l3_code,
            is_new=args.is_new,
            limit=args.limit,
            offset=args.offset,
        )
    except FileNotFoundError as exc:
        print(f"Missing local data: {exc}", file=sys.stderr)
        print("Run: uv run python main.py sync --table ci_member", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
