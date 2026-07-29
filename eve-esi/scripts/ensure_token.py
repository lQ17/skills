#!/usr/bin/env python3
"""Ensure a valid EVE access token (refresh if needed).

Thin wrapper around the shared _common module.

Usage:
  python ensure_token.py
  python ensure_token.py --print-token   # print access token only
  python ensure_token.py --force        # force refresh
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow importing the shared module next to this file
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ensure_token as _ensure_token, TokenError  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Ensure valid EVE access token")
    parser.add_argument("--force", action="store_true", help="Force token refresh")
    parser.add_argument(
        "--print-token", action="store_true", help="Print access token to stdout"
    )
    parser.add_argument(
        "--json", action="store_true", help="Print character meta as JSON"
    )
    args = parser.parse_args()

    try:
        data = _ensure_token(force=args.force)
    except TokenError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.print_token:
        print(data["access_token"])
        return
    if args.json:
        print(
            json.dumps(
                {
                    "character_id": data.get("character_id"),
                    "character_name": data.get("character_name"),
                    "expires_at": data.get("expires_at"),
                    "has_token": bool(data.get("access_token")),
                },
                ensure_ascii=False,
            )
        )
        return
    print(
        f"OK token for {data.get('character_name')} ({data.get('character_id')}), "
        f"expires_at={data.get('expires_at')}"
    )


if __name__ == "__main__":
    main()
