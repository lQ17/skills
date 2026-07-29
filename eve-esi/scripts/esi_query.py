#!/usr/bin/env python3
"""EVE ESI API query helper.

Usage:
    # Auto-token mode (recommended — auto-refreshes expired tokens):
    python esi_query.py --auto-token --endpoint /characters/12345/wallet/

    # Explicit token mode (still supported):
    python esi_query.py --token <ACCESS_TOKEN> --endpoint /characters/12345/wallet/

    # Fetch all pages of assets:
    python esi_query.py --auto-token --endpoint /characters/12345/assets/ --pages

    # POST request (e.g. asset names):
    python esi_query.py --auto-token --endpoint /characters/12345/assets/names/ \
        --method POST --body '[1234567890]'

Requires: Python 3.8+ (uses only stdlib)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow importing the shared module next to this file
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    ESISkillError,
    ESIHTTPError,
    TokenError,
    esi_request,
    esi_request_all_pages,
    ensure_token,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Query EVE ESI API endpoints")
    parser.add_argument(
        "--token",
        default=None,
        help="ESI access token (Bearer). Not needed with --auto-token.",
    )
    parser.add_argument(
        "--auto-token",
        action="store_true",
        help="Auto-fetch and refresh token from saved credentials (recommended)",
    )
    parser.add_argument(
        "--endpoint",
        required=True,
        help="ESI endpoint path, e.g. /characters/12345/wallet/",
    )
    parser.add_argument(
        "--method",
        default="GET",
        choices=["GET", "POST", "PUT", "DELETE"],
        help="HTTP method (default: GET)",
    )
    parser.add_argument(
        "--body", default=None, help="JSON body for POST/PUT requests"
    )
    parser.add_argument(
        "--pages",
        action="store_true",
        help="Automatically fetch all pages (GET only)",
    )
    parser.add_argument(
        "--pretty", action="store_true", help="Pretty-print JSON output"
    )
    args = parser.parse_args()

    # Validate token source
    if not args.token and not args.auto_token:
        parser.error("Either --token or --auto-token is required")

    # Resolve token
    token = args.token
    if token:
        token = token.strip()  # Fix whitespace from Windows piping

    endpoint = args.endpoint
    if not endpoint.startswith("/"):
        endpoint = "/" + endpoint

    # Determine character ID for auto-token mode (used in endpoint substitution)
    char_id = None
    if args.auto_token:
        try:
            creds = ensure_token()
        except TokenError as e:
            print(f"Token error: {e}", file=sys.stderr)
            sys.exit(1)
        token = None  # esi_request will use auto_token=True
        char_id = str(creds.get("character_id") or "")
        # Substitute {char_id} placeholder in endpoint
        if char_id and "{char_id}" in endpoint:
            endpoint = endpoint.replace("{char_id}", char_id)

    try:
        if args.pages and args.method == "GET":
            result = esi_request_all_pages(
                endpoint, token=token, auto_token=args.auto_token
            )
        else:
            result, headers = esi_request(
                endpoint,
                token=token,
                method=args.method,
                body=args.body,
                auto_token=args.auto_token,
            )
            if not args.pages:
                expires = headers.get("expires", "unknown")
                print(f"Cache expires: {expires}", file=sys.stderr)

    except TokenError as e:
        print(f"Token error: {e}", file=sys.stderr)
        print("Run bind_sso.py to re-authorize, or use --auto-token.", file=sys.stderr)
        sys.exit(1)
    except ESIHTTPError as e:
        print(f"HTTP {e.status_code}: {e.body}", file=sys.stderr)
        if e.status_code == 403:
            print(
                "This usually means the required ESI scope is missing. "
                "Re-run bind_sso.py with the needed scope.",
                file=sys.stderr,
            )
        sys.exit(1)
    except ESISkillError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    indent = 2 if args.pretty else None
    if isinstance(result, (dict, list)):
        print(json.dumps(result, indent=indent, ensure_ascii=False))
    else:
        print(result)


if __name__ == "__main__":
    main()
