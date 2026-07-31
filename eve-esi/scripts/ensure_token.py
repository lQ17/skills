#!/usr/bin/env python3
"""Ensure a valid EVE access token (refresh if needed), multi-character aware.

Thin wrapper around the shared _common module.

Usage:
  python ensure_token.py                       # ensure primary token
  python ensure_token.py --char 2124400030     # ensure a specific character
  python ensure_token.py --print-token         # print primary access token
  python ensure_token.py --char 2124400030 --print-token
  python ensure_token.py --force                # force refresh of primary
  python ensure_token.py --list                 # list all bound characters
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Allow importing the shared module next to this file
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    ensure_token as _ensure_token,
    list_characters,
    TokenError,
)


def cmd_list() -> None:
    store = list_characters()
    chars = store.get("characters", {})
    primary = store.get("primary_character_id")
    if not chars:
        print("No characters bound. Run bind_sso.py.")
        return
    print(f"Bound characters ({len(chars)}):")
    for cid, c in chars.items():
        mark = " [PRIMARY]" if cid == primary else ""
        exp = int(c.get("expires_at") or 0)
        status = "valid" if time.time() < exp else "EXPIRED"
        print(f"  - {c.get('character_name', '?')} (id={cid}){mark}  token:{status}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ensure valid EVE access token")
    parser.add_argument("--char", default=None, help="Character ID to act on (default: primary)")
    parser.add_argument("--force", action="store_true", help="Force token refresh")
    parser.add_argument(
        "--print-token", action="store_true", help="Print access token to stdout"
    )
    parser.add_argument(
        "--json", action="store_true", help="Print character meta as JSON"
    )
    parser.add_argument(
        "--list", action="store_true", help="List all bound characters and exit"
    )
    args = parser.parse_args()

    if args.list:
        cmd_list()
        return

    try:
        data = _ensure_token(char_id=args.char, force=args.force)
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
