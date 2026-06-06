#!/usr/bin/env python3
"""Run a zer0share local pro.query call from the command line."""

from __future__ import annotations

import argparse
import json

from zer0share import pro_api


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query local zer0share data.")
    parser.add_argument("api_name", help="Local API name, e.g. daily or stock_basic.")
    parser.add_argument(
        "--params",
        default="{}",
        help="JSON object passed as keyword arguments to pro.query.",
    )
    parser.add_argument(
        "--config",
        default="config/settings.toml",
        help="Path to zer0share settings.toml.",
    )
    parser.add_argument(
        "--head",
        type=int,
        default=20,
        help="Print the first N rows. Use 0 to print all rows.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    params = json.loads(args.params)
    if not isinstance(params, dict):
        raise TypeError("--params must be a JSON object")

    pro = pro_api(args.config)
    df = pro.query(args.api_name, **params)

    print(f"api={args.api_name} rows={len(df)} columns={list(df.columns)}")
    preview = df if args.head == 0 else df.head(args.head)
    print(preview.to_string(index=False))


if __name__ == "__main__":
    main()
