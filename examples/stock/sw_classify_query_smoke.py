from __future__ import annotations

import argparse
import sys

from microshare import pro_api


FIELDS = "index_code,industry_name,level,parent_code,industry_code,is_pub,src"


def _print_frame(title, df, rows: int = 5) -> None:
    print(f"\n## {title}")
    print(f"rows: {len(df)}")
    if df.empty:
        print("(empty)")
        return
    print(df.head(rows).to_string(index=False))


def run_smoke(index_code: str, level: str, src: str, parent_code: str,
              limit: int, offset: int) -> None:
    pro = pro_api()

    print("Sample values")
    print(f"index_code={index_code}  level={level}  src={src}")
    print(f"parent_code={parent_code}  limit={limit}  offset={offset}")

    _print_frame(
        "filter_by_level_L1",
        pro.index_classify(level="L1", fields=FIELDS),
    )
    _print_frame(
        "filter_by_level_L2",
        pro.index_classify(level="L2", fields=FIELDS),
    )
    _print_frame(
        "filter_by_level_L3",
        pro.index_classify(level="L3", fields=FIELDS),
    )
    _print_frame(
        "filter_by_src_SW2021",
        pro.index_classify(src="SW2021", fields=FIELDS),
    )
    _print_frame(
        "filter_by_src_SW2014",
        pro.index_classify(src="SW2014", fields=FIELDS),
    )
    _print_frame(
        "filter_by_index_code",
        pro.index_classify(index_code=index_code, fields=FIELDS),
    )
    _print_frame(
        "filter_by_parent_code",
        pro.index_classify(parent_code=parent_code, fields=FIELDS),
    )
    _print_frame(
        "limit_only",
        pro.index_classify(limit=limit, fields=FIELDS),
    )
    _print_frame(
        "offset_and_limit",
        pro.index_classify(offset=offset, limit=limit, fields=FIELDS),
    )
    _print_frame(
        "no_fields_filter",
        pro.index_classify(level=level),
    )
    _print_frame(
        "query_dispatch",
        pro.query("sw_classify", level=level, src=src, limit=limit, fields=FIELDS),
    )

    # 行业层级分布汇总
    all_df = pro.index_classify(fields="level,src")
    if not all_df.empty:
        print(f"\n## 行业层级分布（共 {len(all_df)} 条）")
        dist = all_df.groupby(["src", "level"]).size().rename("count")
        print(dist.to_string())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke-test sw_classify local query parameters against synced Parquet data."
    )
    parser.add_argument("--index-code", default="801020.SI")
    parser.add_argument("--level", default="L1")
    parser.add_argument("--src", default="SW2021")
    parser.add_argument("--parent-code", default="210000")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--offset", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        run_smoke(
            index_code=args.index_code,
            level=args.level,
            src=args.src,
            parent_code=args.parent_code,
            limit=args.limit,
            offset=args.offset,
        )
    except FileNotFoundError as exc:
        print(f"Missing local data: {exc}", file=sys.stderr)
        print("Run: uv run python main.py sync --table industry", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
