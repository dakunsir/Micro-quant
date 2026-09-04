"""Send one text message through the Feishu application API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make the vendored CLI runnable from a source checkout without an installed package.
repo_root = Path(__file__).resolve().parents[3]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from microshare.feishu_sender import RECEIVE_ID_TYPES, send_text_message


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receive-id", required=True)
    parser.add_argument("--receive-id-type", required=True, choices=RECEIVE_ID_TYPES)
    parser.add_argument("--text", required=True)
    parser.add_argument("--uuid", default=None, help="Idempotency key; a fresh UUID is used by default.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = send_text_message(
        args.receive_id,
        args.receive_id_type,
        args.text,
        uuid=args.uuid,
    )
    print(json.dumps(result, ensure_ascii=False))
    if result.get("success"):
        return 0
    if result.get("error") == "FEISHU_APP_ID and FEISHU_APP_SECRET are required":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
