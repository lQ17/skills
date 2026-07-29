#!/usr/bin/env python3
"""Industry jobs — active, completed, and historical.

Usage:
    python industry.py                    # Show active jobs only
    python industry.py --all              # Show all jobs (active + completed)
    python industry.py --completed        # Show recently completed jobs
    python industry.py --json             # Raw JSON output
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    ACTIVITY_NAMES,
    ESISkillError,
    TokenError,
    esi_request,
    ensure_token,
    format_datetime,
    format_duration,
    resolve_names,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Industry jobs for bound character")
    parser.add_argument(
        "--all", action="store_true", help="Show all jobs (active + completed)"
    )
    parser.add_argument(
        "--completed", action="store_true", help="Show recently completed jobs"
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

    include_completed = args.all or args.completed

    try:
        data, _ = esi_request(
            f"/characters/{char_id}/industry/jobs/",
            auto_token=True,
            # include_completed parameter
            page=None,
        )
        # Re-fetch with include_completed if needed
        if include_completed:
            data, _ = esi_request(
                f"/characters/{char_id}/industry/jobs/?include_completed=true",
                auto_token=True,
            )
    except ESIHTTPError as e:
        print(f"HTTP {e.status_code}: {e.body}", file=sys.stderr)
        sys.exit(1)
    except ESISkillError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, list):
        print("Unexpected response format", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    now = datetime.now(timezone.utc)

    # Split into active and completed
    active = []
    completed = []
    for job in data:
        if not isinstance(job, dict):
            continue
        status = job.get("status", "")
        if status == "active":
            active.append(job)
        elif status in ("delivered", "cancelled", "failed", "paused", "ready"):
            completed.append(job)

    # Sort completed by completion date descending
    completed.sort(
        key=lambda j: j.get("completion_date", j.get("end_date", "")),
        reverse=True,
    )

    # Resolve type names
    all_type_ids = list({
        j.get("blueprint_type_id")
        for j in data
        if j.get("blueprint_type_id")
    })
    type_names = resolve_names(all_type_ids, auto_token=True) if all_type_ids else {}

    # Resolve location names
    all_loc_ids = list({
        j.get("station_id")
        for j in data
        if j.get("station_id")
    })
    # Also check for structure IDs
    for j in data:
        if j.get("facility_id") and j["facility_id"] > 1000000000000:
            all_loc_ids.append(j["facility_id"])
    loc_names = resolve_names(all_loc_ids, auto_token=True) if all_loc_ids else {}

    # Unresolved structures
    for lid in list(all_loc_ids):
        if lid not in loc_names and lid > 1000000000000:
            try:
                resp, _ = esi_request(
                    f"/universe/structures/{lid}/", auto_token=True
                )
                if isinstance(resp, dict) and "name" in resp:
                    loc_names[lid] = resp["name"]
            except ESISkillError:
                loc_names[lid] = f"Structure {lid}"

    print(f"Industry Jobs for {char_name} ({char_id})")
    print(f"  Active: {len(active)} jobs | Completed: {len(completed)} jobs")

    # Show active jobs
    if active:
        print()
        print("Active Jobs:")
        for i, job in enumerate(active, 1):
            bp_id = job.get("blueprint_type_id", 0)
            bp_name = type_names.get(bp_id, f"Type {bp_id}")
            activity = ACTIVITY_NAMES.get(job.get("activity_id", 0), "Unknown")
            runs = job.get("runs", 1)

            # Location
            loc_id = job.get("station_id") or job.get("facility_id", 0)
            loc_name = loc_names.get(loc_id, str(loc_id)) if loc_id else "Unknown"

            # Remaining time
            end_date = job.get("end_date")
            remaining_str = ""
            if end_date:
                try:
                    end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
                    remaining = (end_dt - now).total_seconds()
                    if remaining > 0:
                        remaining_str = f" ({format_duration(remaining)} remaining)"
                    else:
                        remaining_str = " (should be complete)"
                except (ValueError, TypeError):
                    remaining_str = f" (end: {end_date})"

            runs_str = f" x{runs}" if runs > 1 else ""
            print(f"  #{i} {activity}: {bp_name}{runs_str}{remaining_str}")
            print(f"     Location: {loc_name}")
            start = job.get("start_date")
            if start:
                print(f"     Started: {format_datetime(start)}")

    # Show completed jobs
    if args.completed or args.all:
        if completed:
            print()
            if args.all:
                print("Completed Jobs (recent):")
            else:
                print("Completed Jobs:")
            # Show last 20
            for i, job in enumerate(completed[:20], 1):
                bp_id = job.get("blueprint_type_id", 0)
                bp_name = type_names.get(bp_id, f"Type {bp_id}")
                activity = ACTIVITY_NAMES.get(job.get("activity_id", 0), "Unknown")
                status = job.get("status", "unknown")
                runs = job.get("runs", 1)

                end_date = job.get("completion_date") or job.get("end_date", "")
                end_str = format_datetime(end_date) if end_date else "N/A"

                runs_str = f" x{runs}" if runs > 1 else ""
                print(f"  #{i} {activity}: {bp_name}{runs_str} — {status} ({end_str})")

            if len(completed) > 20:
                print(f"  ... and {len(completed) - 20} more completed jobs")
        else:
            print()
            print("No completed jobs found.")


if __name__ == "__main__":
    main()
