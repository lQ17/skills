#!/usr/bin/env python3
"""Character status overview — online, location, ship, clones, implants.

Usage:
    python status.py                     # Full status overview
    python status.py --section location  # Only location info
    python status.py --section ship      # Only ship info
    python status.py --section clones    # Only jump clone info
    python status.py --section implants  # Only active implant info
    python status.py --json              # Raw JSON output
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    ESISkillError,
    TokenError,
    esi_request,
    ensure_token,
    format_datetime,
    resolve_names,
)


def _fetch_section(char_id: str, section: str) -> dict | list | None:
    """Fetch a single section, returning None on scope/permission errors."""
    endpoints = {
        "online": f"/characters/{char_id}/online/",
        "location": f"/characters/{char_id}/location/",
        "ship": f"/characters/{char_id}/ship/",
        "clones": f"/characters/{char_id}/clones/",
        "implants": f"/characters/{char_id}/implants/",
    }
    try:
        data, _ = esi_request(endpoints[section], auto_token=True)
        return data
    except ESISkillError as e:
        return {"_error": str(e)}


def _resolve_location(location_id: int) -> str:
    """Resolve a station/structure/system ID to a name."""
    # Try universe/names first (works for stations, systems, agents)
    names = resolve_names([location_id], auto_token=True)
    if location_id in names:
        return names[location_id]
    # Try as a player structure (requires auth)
    if location_id > 1000000000000:
        try:
            resp, _ = esi_request(
                f"/universe/structures/{location_id}/", auto_token=True
            )
            if isinstance(resp, dict) and "name" in resp:
                return resp["name"]
        except ESISkillError:
            pass
    return f"ID:{location_id}"


def _format_online(data: dict | list) -> str:
    lines = ["Online Status:"]
    if isinstance(data, list):
        lines.append("  (unexpected list response)")
        return "\n".join(lines)
    if isinstance(data, dict) and data.get("_error"):
        lines.append(f"  (unavailable: {data['_error']})")
        return "\n".join(lines)
    online = data.get("online", False)
    lines.append(f"  Online: {'Yes' if online else 'No'}")
    if data.get("last_login"):
        lines.append(f"  Last login: {format_datetime(data['last_login'])}")
    if data.get("last_logout"):
        lines.append(f"  Last logout: {format_datetime(data['last_logout'])}")
    lines.append(f"  Logins: {data.get('logins', 'N/A')}")
    return "\n".join(lines)


def _format_location(data: dict | list) -> str:
    lines = ["Location:"]
    if isinstance(data, list):
        lines.append("  (unexpected list response)")
        return "\n".join(lines)
    if isinstance(data, dict) and data.get("_error"):
        lines.append(f"  (unavailable: {data['_error']})")
        return "\n".join(lines)
    # Resolve IDs
    ids_to_resolve = []
    if data.get("solar_system_id"):
        ids_to_resolve.append(data["solar_system_id"])
    if data.get("station_id"):
        ids_to_resolve.append(data["station_id"])
    if data.get("structure_id"):
        ids_to_resolve.append(data["structure_id"])
    names = resolve_names(ids_to_resolve, auto_token=True) if ids_to_resolve else {}

    if data.get("solar_system_id"):
        sys_name = names.get(data["solar_system_id"], str(data["solar_system_id"]))
        lines.append(f"  System: {sys_name}")
    if data.get("station_id"):
        sta_name = names.get(data["station_id"], str(data["station_id"]))
        lines.append(f"  Station: {sta_name}")
    if data.get("structure_id"):
        struct_name = names.get(data["structure_id"], str(data["structure_id"]))
        lines.append(f"  Structure: {struct_name}")
    return "\n".join(lines)


def _clean_name(name: str) -> str:
    """Clean up ESI name strings that may contain Python repr artifacts."""
    if not isinstance(name, str):
        return str(name)
    # Handle ESI returning names like u'冲冲冲' as a string
    # This happens when a character named their ship with a Python 2 repr-style string
    if name.startswith("u'") and name.endswith("'"):
        try:
            import ast
            cleaned = ast.literal_eval(name)
            if isinstance(cleaned, str):
                return cleaned
        except (ValueError, SyntaxError):
            pass
    if name.startswith('u"') and name.endswith('"'):
        try:
            import ast
            cleaned = ast.literal_eval(name)
            if isinstance(cleaned, str):
                return cleaned
        except (ValueError, SyntaxError):
            pass
    return name


def _format_ship(data: dict | list) -> str:
    lines = ["Current Ship:"]
    if isinstance(data, list):
        lines.append("  (unexpected list response)")
        return "\n".join(lines)
    if isinstance(data, dict) and data.get("_error"):
        lines.append(f"  (unavailable: {data['_error']})")
        return "\n".join(lines)
    ship_type_id = data.get("ship_type_id")
    ship_name = data.get("ship_name", "Unknown")
    # Clean up ESI repr-style names like u'冲冲冲'
    ship_name = _clean_name(ship_name)
    if ship_type_id:
        type_name = resolve_names([ship_type_id], auto_token=True).get(
            ship_type_id, str(ship_type_id)
        )
        lines.append(f"  Type: {type_name}")
    else:
        lines.append(f"  Type ID: N/A")
    lines.append(f"  Name: {ship_name}")
    if data.get("ship_item_id"):
        lines.append(f"  Item ID: {data['ship_item_id']}")
    return "\n".join(lines)


def _format_clones(data: dict | list) -> str:
    lines = ["Jump Clones:"]
    if isinstance(data, dict) and data.get("_error"):
        lines.append(f"  (unavailable: {data['_error']})")
        return "\n".join(lines)
    if isinstance(data, list):
        return "\n".join(lines + ["  (raw list data)"])
    clones = data.get("jump_clones", [])
    lines.append(f"  Total: {len(clones)}")
    if data.get("home_location"):
        home = data["home_location"]
        loc_id = home.get("location_id", "N/A")
        loc_type = home.get("location_type", "N/A")
        loc_name = _resolve_location(loc_id) if isinstance(loc_id, int) else str(loc_id)
        lines.append(f"  Home: {loc_name} ({loc_type})")

    for i, clone in enumerate(clones, 1):
        loc_id = clone.get("location_id", "N/A")
        loc_name = _resolve_location(loc_id) if isinstance(loc_id, int) else str(loc_id)
        implant_ids = clone.get("implants", [])
        implant_str = ""
        if implant_ids:
            imp_names = resolve_names(implant_ids, auto_token=True)
            names_list = [imp_names.get(iid, str(iid)) for iid in implant_ids]
            implant_str = f" — implants: {', '.join(names_list)}"
        lines.append(f"  #{i}: {loc_name}{implant_str}")
    return "\n".join(lines)


def _format_implants(data: dict | list) -> str:
    lines = ["Active Implants:"]
    # /characters/{id}/implants/ returns a raw list of type IDs
    if isinstance(data, list):
        implant_ids = data
    elif isinstance(data, dict) and data.get("_error"):
        lines.append(f"  (unavailable: {data['_error']})")
        return "\n".join(lines)
    else:
        implant_ids = data.get("implants", []) if isinstance(data, dict) else []
    if not implant_ids:
        lines.append("  None")
    else:
        names = resolve_names(implant_ids, auto_token=True)
        for i, iid in enumerate(implant_ids, 1):
            name = names.get(iid, str(iid))
            lines.append(f"  Slot {i}: {name}")
        lines.append(f"  Total: {len(implant_ids)}")
    return "\n".join(lines)


SECTION_FORMATTERS = {
    "online": _format_online,
    "location": _format_location,
    "ship": _format_ship,
    "clones": _format_clones,
    "implants": _format_implants,
}

ALL_SECTIONS = ["online", "location", "ship", "clones", "implants"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Character status overview (online, location, ship, clones, implants)"
    )
    parser.add_argument(
        "--section",
        choices=ALL_SECTIONS,
        help="Show only one section (default: all)",
    )
    parser.add_argument(
        "--json", action="store_true", help="Output raw JSON"
    )
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

    sections = [args.section] if args.section else ALL_SECTIONS

    raw_data: dict = {
        "character_id": int(char_id) if str(char_id).isdigit() else char_id,
        "character_name": char_name,
    }

    for section in sections:
        raw_data[section] = _fetch_section(char_id, section)

    if args.json:
        print(json.dumps(raw_data, indent=2, ensure_ascii=False))
        return

    # Formatted text output
    print(f"Character: {char_name} ({char_id})")
    print()
    for section in sections:
        formatter = SECTION_FORMATTERS[section]
        data = raw_data.get(section, {})
        print(formatter(data))
        print()


if __name__ == "__main__":
    main()
