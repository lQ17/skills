#!/usr/bin/env python3
"""Asset overview — summary, search, location filter.

Usage:
    python assets.py                    # Summary: item count by location
    python assets.py --search "raven"   # Find items matching name
    python assets.py --location "jita"  # Filter by location name
    python assets.py --summary          # Detailed location breakdown
    python assets.py --json             # Raw JSON output
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    ESISkillError,
    TokenError,
    esi_request,
    esi_request_all_pages,
    ensure_token,
    resolve_names,
)


def _resolve_location_id(location_id: int, auto_token: bool = True) -> str:
    """Resolve a location ID to a name.

    Station IDs are in the 60000000-69999999 range.
    Structure IDs are 64-bit integers typically > 1000000000000.
    System IDs are in the 30000000-39999999 range.
    """
    # Try universe/names first (works for stations and some structures)
    names = resolve_names([location_id], auto_token=auto_token)
    if location_id in names:
        return names[location_id]

    # Try as a structure
    if location_id > 1000000000000:
        try:
            resp, _ = esi_request(
                f"/universe/structures/{location_id}/", auto_token=auto_token
            )
            if isinstance(resp, dict) and "name" in resp:
                return resp["name"]
        except ESISkillError:
            pass

    return str(location_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Asset overview for bound character")
    parser.add_argument(
        "--search", metavar="TERM", help="Search items by name (case-insensitive)"
    )
    parser.add_argument(
        "--location", metavar="TERM", help="Filter by location name (case-insensitive)"
    )
    parser.add_argument(
        "--summary", action="store_true", help="Detailed location breakdown"
    )
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    try:
        creds = ensure_token()
    except TokenError as e:
        print(f"Token error: {e}", file=sys.stderr)
        sys.exit(1)

    char_id = creds.get("character_id") or ""
    char_name = creds.get("character_name") or "Unknown"
    if not char_id:
        print("Error: character_id missing; re-run bind_sso.py", file=sys.stderr)
        sys.exit(1)

    try:
        # Fetch all assets (paginated)
        print("Fetching assets...", file=sys.stderr)
        assets = esi_request_all_pages(
            f"/characters/{char_id}/assets/", auto_token=True
        )
    except ESIHTTPError as e:
        print(f"HTTP {e.status_code}: {e.body}", file=sys.stderr)
        sys.exit(1)
    except ESISkillError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(assets, list):
        print("Unexpected response format", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(assets, indent=2, ensure_ascii=False))
        return

    if not assets:
        print(f"Assets for {char_name} ({char_id})")
        print("  No assets found.")
        return

    # Collect all unique type IDs and location IDs for resolution
    type_ids = list({a.get("type_id") for a in assets if a.get("type_id")})
    location_ids = list({a.get("location_id") for a in assets if a.get("location_id")})

    print(f"Resolving {len(type_ids)} type names...", file=sys.stderr)
    type_names = resolve_names(type_ids, auto_token=True) if type_ids else {}

    # Resolve location names in batches
    print(f"Resolving {len(location_ids)} location names...", file=sys.stderr)
    location_names: dict[int, str] = {}
    # Batch resolve via universe/names (works for stations, systems, some structures)
    loc_batch = {}
    for lid in location_ids:
        if lid < 1000000000000:  # Not a player structure
            loc_batch[lid] = lid
        else:
            # Player structures need individual lookups
            location_names[lid] = _resolve_location_id(lid, auto_token=True)

    if loc_batch:
        batch_names = resolve_names(list(loc_batch.keys()), auto_token=True)
        location_names.update(batch_names)

    # Fill in unresolved location IDs
    for lid in location_ids:
        if lid not in location_names:
            location_names[lid] = str(lid)

    # --- Search mode ---
    if args.search:
        term = args.search.lower()
        matches = []
        for a in assets:
            tid = a.get("type_id", 0)
            name = type_names.get(tid, "")
            if term in name.lower():
                loc_id = a.get("location_id", 0)
                loc_name = location_names.get(loc_id, str(loc_id))
                matches.append((name, loc_name, a.get("quantity", 1), a.get("item_id", 0)))

        print(f"Assets matching '{args.search}' for {char_name} ({char_id})")
        if matches:
            for name, loc, qty, item_id in matches:
                if qty > 1:
                    print(f"  {name} x{qty} — {loc}")
                else:
                    print(f"  {name} — {loc}")
            print(f"\n  Found {len(matches)} item(s)")
        else:
            print(f"  No items matching '{args.search}'")
        return

    # --- Location filter ---
    if args.location:
        term = args.location.lower()
        filtered = []
        for a in assets:
            loc_id = a.get("location_id", 0)
            loc_name = location_names.get(loc_id, str(loc_id))
            if term in loc_name.lower():
                tid = a.get("type_id", 0)
                name = type_names.get(tid, f"Type {tid}")
                filtered.append((name, loc_name, a.get("quantity", 1)))

        print(f"Assets at locations matching '{args.location}' for {char_name} ({char_id})")
        if filtered:
            for name, loc, qty in filtered:
                if qty > 1:
                    print(f"  {name} x{qty}")
                else:
                    print(f"  {name}")
            print(f"\n  Found {len(filtered)} item(s)")
        else:
            print(f"  No items at locations matching '{args.location}'")
        return

    # --- Default: summary by location ---
    by_location: dict[int, list] = defaultdict(list)
    for a in assets:
        loc_id = a.get("location_id", 0)
        by_location[loc_id].append(a)

    print(f"Assets for {char_name} ({char_id})")
    print(f"  Total items: {len(assets):,}")
    print()

    # Sort locations by item count descending
    sorted_locs = sorted(by_location.items(), key=lambda x: len(x[1]), reverse=True)

    if args.summary:
        print("By Location:")
        for loc_id, items in sorted_locs:
            loc_name = location_names.get(loc_id, str(loc_id))
            print(f"  {loc_name}: {len(items):,} items")
    else:
        # Compact summary — top 5 locations + "other"
        print("Top Locations:")
        for loc_id, items in sorted_locs[:5]:
            loc_name = location_names.get(loc_id, str(loc_id))
            print(f"  {loc_name}: {len(items):,} items")
        if len(sorted_locs) > 5:
            other_count = sum(len(items) for _, items in sorted_locs[5:])
            print(f"  ({len(sorted_locs) - 5} other locations, {other_count:,} items)")

        print()
        print("Use --search <name> to find specific items")
        print("Use --location <name> to filter by location")
        print("Use --summary for full location breakdown")


if __name__ == "__main__":
    main()
