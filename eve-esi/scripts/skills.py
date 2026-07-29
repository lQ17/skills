#!/usr/bin/env python3
"""Skill information — total SP, skill queue, trained skills.

Usage:
    python skills.py                    # Skill summary + active queue
    python skills.py --queue            # Detailed skill queue view
    python skills.py --search "mining"  # Search trained skills by name
    python skills.py --json             # Raw JSON output
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    ESISkillError,
    TokenError,
    esi_request,
    ensure_token,
    format_datetime,
    format_duration,
    resolve_names,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Skill information for bound character")
    parser.add_argument(
        "--queue", action="store_true", help="Show detailed skill queue"
    )
    parser.add_argument(
        "--search", metavar="TERM", help="Search trained skills by name (case-insensitive)"
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

    results: dict = {
        "character_id": int(char_id) if str(char_id).isdigit() else char_id,
        "character_name": char_name,
    }

    try:
        # Fetch skills
        skills_data, _ = esi_request(
            f"/characters/{char_id}/skills/", auto_token=True
        )
        results["skills"] = skills_data

        # Fetch skill queue
        queue_data, _ = esi_request(
            f"/characters/{char_id}/skillqueue/", auto_token=True
        )
        results["skillqueue"] = queue_data

        # Fetch attributes
        try:
            attrs_data, _ = esi_request(
                f"/characters/{char_id}/attributes/", auto_token=True
            )
            results["attributes"] = attrs_data
        except ESISkillError:
            results["attributes"] = None

    except ESIHTTPError as e:
        print(f"HTTP {e.status_code}: {e.body}", file=sys.stderr)
        sys.exit(1)
    except ESISkillError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return

    # --- Formatted output ---
    skills = skills_data if isinstance(skills_data, dict) else {}
    queue = queue_data if isinstance(queue_data, list) else []
    attrs = results.get("attributes")

    total_sp = skills.get("total_sp", 0)
    trained_skills = skills.get("skills", [])
    skill_count = len(trained_skills)
    level_v_count = sum(1 for s in trained_skills if s.get("trained_skill_level", 0) == 5)

    print(f"Skill Summary for {char_name} ({char_id})")
    print(f"  Total SP:         {total_sp:,}")
    print(f"  Skills trained:   {skill_count} ({level_v_count} at level V)")

    # Active queue analysis
    now = datetime.now(timezone.utc)
    active_queue = []
    for entry in queue:
        if not isinstance(entry, dict):
            continue
        finish = entry.get("finish_date")
        start = entry.get("start_date")
        if not start:
            continue
        if finish:
            try:
                finish_dt = datetime.fromisoformat(finish.replace("Z", "+00:00"))
                if finish_dt > now:
                    active_queue.append(entry)
            except (ValueError, TypeError):
                active_queue.append(entry)
        elif start:
            # Paused or not yet started — still in queue
            try:
                start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                if start_dt <= now:
                    active_queue.append(entry)
            except (ValueError, TypeError):
                pass

    if active_queue:
        # Calculate total remaining time from the last finishing skill
        last_finish = None
        for entry in active_queue:
            finish = entry.get("finish_date")
            if finish:
                try:
                    finish_dt = datetime.fromisoformat(finish.replace("Z", "+00:00"))
                    if last_finish is None or finish_dt > last_finish:
                        last_finish = finish_dt
                except (ValueError, TypeError):
                    pass

        if last_finish:
            remaining = (last_finish - now).total_seconds()
            print(f"  Active queue:     {len(active_queue)} skills ({format_duration(remaining)} remaining)")
        else:
            print(f"  Active queue:     {len(active_queue)} skills")
    else:
        print(f"  Active queue:     Empty")

    # Currently training (first unfinished entry)
    print()
    training = [e for e in active_queue if e.get("start_date")]
    if training:
        print("Currently Training:")
        # Resolve skill type IDs to names
        skill_ids = [e.get("skill_id") for e in training if e.get("skill_id")]
        skill_names = resolve_names(skill_ids, auto_token=True) if skill_ids else {}

        for i, entry in enumerate(training[:5], 1):  # Show up to 5
            sid = entry.get("skill_id", 0)
            name = skill_names.get(sid, f"Skill {sid}")
            level = entry.get("finished_level", "?")
            finish = entry.get("finish_date")
            if finish:
                try:
                    finish_dt = datetime.fromisoformat(finish.replace("Z", "+00:00"))
                    remaining = (finish_dt - now).total_seconds()
                    print(f"  {i}. {name} Lv{level} ({format_duration(remaining)} remaining)")
                except (ValueError, TypeError):
                    print(f"  {i}. {name} Lv{level} (finish: {finish})")
            else:
                start = entry.get("start_date", "")
                print(f"  {i}. {name} Lv{level} (queued, not yet started)")

        if len(training) > 5:
            print(f"  ... and {len(training) - 5} more")

    # --queue flag: detailed queue view
    if args.queue:
        print()
        print("Full Skill Queue:")
        skill_ids_all = [e.get("skill_id") for e in queue if e.get("skill_id")]
        skill_names_all = resolve_names(skill_ids_all, auto_token=True) if skill_ids_all else {}

        for i, entry in enumerate(queue, 1):
            sid = entry.get("skill_id", 0)
            name = skill_names_all.get(sid, f"Skill {sid}")
            level = entry.get("finished_level", "?")
            start = entry.get("start_date", "N/A")
            finish = entry.get("finish_date")

            if finish:
                try:
                    finish_dt = datetime.fromisoformat(finish.replace("Z", "+00:00"))
                    if finish_dt < now:
                        status = "✓ completed"
                    else:
                        remaining = (finish_dt - now).total_seconds()
                        status = f"{format_duration(remaining)} remaining"
                except (ValueError, TypeError):
                    status = f"finish: {finish}"
            elif start:
                try:
                    start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    if start_dt > now:
                        status = "queued"
                    else:
                        status = "paused"
                except (ValueError, TypeError):
                    status = "unknown"
            else:
                status = "empty slot"

            print(f"  {i:2d}. {name} Lv{level} — {status}")

    # Attributes
    if attrs and isinstance(attrs, dict):
        print()
        print("Attributes:")
        attr_names = {
            "intelligence": "Intelligence",
            "memory": "Memory",
            "charisma": "Charisma",
            "perception": "Perception",
            "willpower": "Willpower",
        }
        parts = []
        for key, label in attr_names.items():
            val = attrs.get(key)
            if val is not None:
                parts.append(f"{label}: {val}")
        if parts:
            print(f"  {' | '.join(parts)}")

        # Bonus remaps available
        remaps = attrs.get("bonus_remaps")
        if remaps is not None:
            print(f"  Bonus remaps: {remaps}")
        last_remap = attrs.get("last_remap_date")
        if last_remap:
            print(f"  Last remap: {format_datetime(last_remap)}")

    # --search flag: search trained skills
    if args.search:
        term = args.search.lower()
        print()
        print(f"Skills matching '{args.search}':")
        skill_ids_search = [s.get("skill_id") for s in trained_skills if s.get("skill_id")]
        skill_names_search = resolve_names(skill_ids_search, auto_token=True) if skill_ids_search else {}

        matches = []
        for s in trained_skills:
            sid = s.get("skill_id", 0)
            name = skill_names_search.get(sid, "")
            if term in name.lower():
                active_level = s.get("trained_skill_level", 0)
                sp = s.get("skillpoints_in_skill", 0)
                matches.append((name, active_level, sp))

        if matches:
            for name, level, sp in matches:
                print(f"  {name} Lv{level} ({sp:,} SP)")
            print(f"  Found {len(matches)} skill(s)")
        else:
            print(f"  No skills matching '{args.search}'")


if __name__ == "__main__":
    main()
