#!/usr/bin/env python3
"""Query wallet balance + journal + transactions for the bound character.

Usage:
    python wallet_journal.py                  # Show balance + recent journal
    python wallet_journal.py --what balance   # Balance only
    python wallet_journal.py --what journal   # Journal entries (page 1)
    python wallet_journal.py --what journal --pages  # All journal pages
    python wallet_journal.py --what transactions
    python wallet_journal.py --json           # Raw JSON output
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow importing helpers next to this file
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    ESISkillError,
    TokenError,
    esi_request,
    esi_request_all_pages,
    ensure_token,
    format_isk,
    format_isk_full,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Query bound character wallet")
    parser.add_argument(
        "--what",
        choices=["balance", "journal", "transactions", "all"],
        default="balance",
    )
    parser.add_argument("--pages", action="store_true", help="Fetch all journal pages")
    parser.add_argument("--char", default=None, help="Character ID (default: primary)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output"
    )
    args = parser.parse_args()

    try:
        data = ensure_token(char_id=args.char)
    except TokenError as e:
        print(f"Token error: {e}", file=sys.stderr)
        sys.exit(1)

    use_auto = args.char is None
    token = None if use_auto else data.get("access_token")
    char_id = data.get("character_id") or ""
    char_name = data.get("character_name") or "Unknown"
    if not char_id:
        print("Error: character_id missing; re-run bind_sso.py", file=sys.stderr)
        sys.exit(1)

    results: dict = {
        "character_id": int(char_id) if str(char_id).isdigit() else char_id,
        "character_name": char_name,
    }

    try:
        if args.what in ("balance", "all"):
            bal, _ = esi_request(
                f"/characters/{char_id}/wallet/", token=token, auto_token=use_auto
            )
            results["balance"] = bal

        if args.what in ("journal", "all"):
            if args.pages:
                results["journal"] = esi_request_all_pages(
                    f"/characters/{char_id}/wallet/journal/",
                    token=token,
                    auto_token=use_auto,
                )
            else:
                j, _ = esi_request(
                    f"/characters/{char_id}/wallet/journal/",
                    page=1,
                    token=token,
                    auto_token=use_auto,
                )
                results["journal"] = j

        if args.what in ("transactions", "all"):
            tx, _ = esi_request(
                f"/characters/{char_id}/wallet/transactions/",
                token=token,
                auto_token=use_auto,
            )
            results["transactions"] = tx

    except ESIHTTPError as e:
        print(f"HTTP {e.status_code}: {e.body}", file=sys.stderr)
        sys.exit(1)
    except ESISkillError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json or args.what != "balance":
        indent = 2 if args.pretty else None
        print(json.dumps(results, indent=indent, ensure_ascii=False))
    else:
        # Pretty-print balance for the default "balance" view
        bal = results.get("balance", 0)
        print(f"  Character: {char_name} ({char_id})")
        print(f"  Balance:   {format_isk(bal)} ISK ({format_isk_full(bal)})")


if __name__ == "__main__":
    main()
