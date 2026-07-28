#!/usr/bin/env python3
"""Query wallet balance + journal + transactions for the bound character."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Allow importing helpers next to this file
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ensure_token  # noqa: E402
import esi_query  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Query bound character wallet journal")
    parser.add_argument(
        "--what",
        choices=["balance", "journal", "transactions", "all"],
        default="all",
    )
    parser.add_argument("--pages", action="store_true", help="Fetch all journal pages")
    parser.add_argument("--pretty", action="store_true", default=True)
    args = parser.parse_args()

    data = ensure_token.ensure()
    token = data["access_token"]
    char_id = data.get("character_id") or os.environ.get("EVE_CHAR_ID")
    if not char_id:
        raise SystemExit("character_id missing; re-run bind_sso.py")

    out: dict = {
        "character_id": char_id,
        "character_name": data.get("character_name"),
    }

    if args.what in ("balance", "all"):
        bal, _ = esi_query.esi_request(f"/characters/{char_id}/wallet/", token)
        out["balance"] = bal

    if args.what in ("journal", "all"):
        if args.pages or args.what == "all":
            out["journal"] = esi_query.esi_request_all_pages(
                f"/characters/{char_id}/wallet/journal/", token
            )
        else:
            j, _ = esi_query.esi_request(
                f"/characters/{char_id}/wallet/journal/", token, page=1
            )
            out["journal"] = j

    if args.what in ("transactions", "all"):
        tx, _ = esi_query.esi_request(
            f"/characters/{char_id}/wallet/transactions/", token
        )
        out["transactions"] = tx

    print(json.dumps(out, indent=2 if args.pretty else None, ensure_ascii=False))


if __name__ == "__main__":
    main()
