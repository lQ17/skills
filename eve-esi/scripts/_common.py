#!/usr/bin/env python3
"""Shared utilities for EVE ESI skill scripts.

Provides:
  - Unified constants (SSO URLs, BASE_URL, USER_AGENT, scopes)
  - Credential management (load, save, ensure valid token)
  - Core HTTP request function with auto-refresh and retry
  - Output formatting (ISK, datetime, duration)
  - Type ID name resolution with caching
  - Custom exceptions (no sys.exit in library code)

All scripts import from this module. CLI entry points catch exceptions
and exit with friendly messages; library callers can handle them.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SSO_AUTHORIZE_URL = "https://login.eveonline.com/v2/oauth/authorize"
SSO_TOKEN_URL = "https://login.eveonline.com/v2/oauth/token"
SSO_VERIFY_URL = "https://login.eveonline.com/oauth/verify"
BASE_URL = "https://esi.evetech.net/latest"
USER_AGENT = "OpenClaw-ESI-Skill/1.0 (https://github.com/openclaw/openclaw)"

DEFAULT_SCOPES = [
    "esi-wallet.read_character_wallet.v1",
    "esi-assets.read_assets.v1",
    "esi-skills.read_skills.v1",
    "esi-skills.read_skillqueue.v1",
    "esi-clones.read_clones.v1",
    "esi-clones.read_implants.v1",
    "esi-location.read_location.v1",
    "esi-location.read_ship_type.v1",
    "esi-location.read_online.v1",
    "esi-characters.read_notifications.v1",
    "esi-industry.read_character_jobs.v1",
    "esi-markets.read_character_orders.v1",
    "esi-contracts.read_character_contracts.v1",
    "esi-killmails.read_killmails.v1",
    "esi-planets.manage_planets.v1",
    "esi-characters.read_fatigue.v1",
    "esi-mail.read_mail.v1",
    "esi-characters.read_blueprints.v1",
    "esi-characters.read_loyalty.v1",
    "esi-industry.read_character_mining.v1",
    "esi-fittings.read_fittings.v1",
    "esi-characters.read_standings.v1",
]

WALLET_SCOPES = ["esi-wallet.read_character_wallet.v1"]

SCOPE_PRESETS = {
    "default": DEFAULT_SCOPES,
    "wallet": WALLET_SCOPES,
    "full": DEFAULT_SCOPES,
}

# Industry activity ID -> name mapping
ACTIVITY_NAMES = {
    1: "Manufacturing",
    2: "Researching Time Efficiency",
    3: "Researching Material Efficiency",
    4: "Copying",
    5: "Inventing",
    8: "Reversal Engineering",
    9: "Reactions",
    11: "Reactions",
}

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ESISkillError(Exception):
    """Base exception for ESI skill errors."""


class TokenError(ESISkillError):
    """Token is missing, expired, or refresh failed."""


class ESIHTTPError(ESISkillError):
    """HTTP error from ESI API."""

    def __init__(self, status_code: int, body: str, headers: dict | None = None):
        self.status_code = status_code
        self.body = body
        self.headers = headers or {}
        super().__init__(f"HTTP {status_code}: {body[:200]}")


class RateLimitError(ESIHTTPError):
    """HTTP 420 — ESI rate limited."""


# ---------------------------------------------------------------------------
# Credential management
# ---------------------------------------------------------------------------


def cred_path() -> Path:
    """Return the path to the credentials file."""
    return Path.home() / ".eve-esi" / "credentials.json"


def load_creds() -> dict:
    """Load credentials from file and overlay with environment variables."""
    path = cred_path()
    data: dict = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    # Env overrides / fills missing values
    data.setdefault("client_id", os.environ.get("EVE_CLIENT_ID", ""))
    data.setdefault("client_secret", os.environ.get("EVE_CLIENT_SECRET", ""))
    data.setdefault("access_token", os.environ.get("EVE_TOKEN_MAIN", ""))
    data.setdefault("refresh_token", os.environ.get("EVE_REFRESH_MAIN", ""))
    data.setdefault("character_id", os.environ.get("EVE_CHAR_ID", ""))
    data.setdefault("character_name", os.environ.get("EVE_CHAR_NAME", ""))
    data.setdefault("expires_at", 0)
    return data


def set_windows_user_env(name: str, value: str) -> None:
    """Persist User env var on Windows; also set process env for this session."""
    os.environ[name] = value
    if sys.platform != "win32":
        return
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Environment",
            0,
            winreg.KEY_SET_VALUE,
        )
        try:
            winreg.SetValueEx(key, name, 0, winreg.REG_EXPAND_SZ, value)
        finally:
            winreg.CloseKey(key)
        try:
            import ctypes

            HWND_BROADCAST = 0xFFFF
            WM_SETTINGCHANGE = 0x001A
            SMTO_ABORTIFHUNG = 0x0002
            result = ctypes.c_long()
            ctypes.windll.user32.SendMessageTimeoutW(
                HWND_BROADCAST,
                WM_SETTINGCHANGE,
                0,
                "Environment",
                SMTO_ABORTIFHUNG,
                5000,
                ctypes.byref(result),
            )
        except Exception:
            pass
    except Exception as e:
        print(f"Warning: could not persist env {name}: {e}", file=sys.stderr)


def save_creds(data: dict) -> None:
    """Save credentials to file and update Windows User env vars."""
    path = cred_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    # Restrict file permissions on Windows
    if sys.platform == "win32":
        try:
            subprocess.run(
                [
                    "icacls",
                    str(path),
                    "/inheritance:r",
                    "/grant:r",
                    f"{os.environ.get('USERNAME', '')}:(R,W)",
                ],
                capture_output=True,
                check=False,
            )
        except Exception:
            pass
    # Update env vars
    if data.get("client_id"):
        set_windows_user_env("EVE_CLIENT_ID", str(data["client_id"]))
    if data.get("client_secret"):
        set_windows_user_env("EVE_CLIENT_SECRET", str(data["client_secret"]))
    if data.get("access_token"):
        set_windows_user_env("EVE_TOKEN_MAIN", str(data["access_token"]))
    if data.get("refresh_token"):
        set_windows_user_env("EVE_REFRESH_MAIN", str(data["refresh_token"]))
    if data.get("character_id"):
        set_windows_user_env("EVE_CHAR_ID", str(data["character_id"]))
    if data.get("character_name"):
        set_windows_user_env("EVE_CHAR_NAME", str(data["character_name"]))


# ---------------------------------------------------------------------------
# Multi-character credential store
# ---------------------------------------------------------------------------
#
# Layout of ~/.eve-esi/credentials.json:
#   {
#     "primary_character_id": "2124400030",
#     "characters": {
#       "<character_id>": { client_id, character_id, character_name, scopes,
#                          access_token, refresh_token, expires_at, ... },
#       ...
#     }
#   }
# Legacy flat (single-character) files are migrated automatically on load.

def load_store() -> dict:
    """Load the multi-character store, migrating legacy flat format if needed."""
    path = cred_path()
    if not path.exists():
        return {"primary_character_id": None, "characters": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"primary_character_id": None, "characters": {}}

    if not isinstance(data.get("characters"), dict):
        chars: dict[str, dict] = {}
        cid = data.get("character_id")
        if cid is not None:
            cid_str = str(cid)
            slot = dict(data)
            slot["character_id"] = cid
            chars[cid_str] = slot
        data = {
            "primary_character_id": cid_str if cid is not None else None,
            "characters": chars,
        }

    data.setdefault("characters", {})
    if not data.get("primary_character_id") and data["characters"]:
        data["primary_character_id"] = next(iter(data["characters"]))
    return data


def save_store(data: dict) -> Path:
    """Persist the multi-character store and tighten file ACLs on Windows."""
    path = cred_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    if sys.platform == "win32":
        try:
            subprocess.run(
                [
                    "icacls",
                    str(path),
                    "/inheritance:r",
                    "/grant:r",
                    f"{os.environ.get('USERNAME', '')}:(R,W)",
                ],
                capture_output=True,
                check=False,
            )
        except Exception:
            pass
    return path


def get_char(store: dict, char_id=None):
    """Resolve (character_id_str, slot_dict) for a given id or the primary."""
    chars = store.get("characters", {})
    if not chars:
        return None, None
    cid = char_id or store.get("primary_character_id") or next(iter(chars))
    cid = str(cid)
    return cid, chars.get(cid)


def sync_env_for_char(char_slot: dict) -> None:
    """Mirror a character's credentials into the single-value Windows env slots.

    Keeps the existing dashboard config ($ENV:EVE_TOKEN_MAIN etc.) working for
    the active/primary character.
    """
    if not char_slot:
        return
    if char_slot.get("client_id"):
        set_windows_user_env("EVE_CLIENT_ID", str(char_slot["client_id"]))
    if char_slot.get("client_secret"):
        set_windows_user_env("EVE_CLIENT_SECRET", str(char_slot["client_secret"]))
    if char_slot.get("access_token"):
        set_windows_user_env("EVE_TOKEN_MAIN", str(char_slot["access_token"]))
    if char_slot.get("refresh_token"):
        set_windows_user_env("EVE_REFRESH_MAIN", str(char_slot["refresh_token"]))
    if char_slot.get("character_id"):
        set_windows_user_env("EVE_CHAR_ID", str(char_slot["character_id"]))
    if char_slot.get("character_name"):
        set_windows_user_env("EVE_CHAR_NAME", str(char_slot["character_name"]))


def add_character(payload: dict, set_primary: bool = False) -> dict:
    """Insert/update a character slot in the store. Returns the updated store.

    Does NOT delete other characters. Sets the character as primary when
    *set_primary* is True or when no primary exists yet, and mirrors the
    primary's credentials into the Windows env slots.
    """
    store = load_store()
    cid = str(payload.get("character_id") or "")
    if not cid:
        raise TokenError("payload missing character_id")
    store["characters"][cid] = payload
    if set_primary or not store.get("primary_character_id"):
        store["primary_character_id"] = cid
    save_store(store)
    if store["primary_character_id"] == cid:
        sync_env_for_char(payload)
    return store


def list_characters() -> dict:
    """Return the full store (callers format/print as needed)."""
    return load_store()


# ---------------------------------------------------------------------------
# Token management
# ---------------------------------------------------------------------------


def _refresh_token(data: dict) -> dict:
    """Refresh an expired access token. Raises TokenError on failure."""
    if not data.get("client_id") or not data.get("refresh_token"):
        raise TokenError("Missing client_id or refresh_token. Run bind_sso.py first.")

    form = {
        "grant_type": "refresh_token",
        "refresh_token": data["refresh_token"],
    }
    headers: dict[str, str] = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": USER_AGENT,
        "Host": "login.eveonline.com",
    }
    if data.get("client_secret"):
        basic = base64.b64encode(
            f"{data['client_id']}:{data['client_secret']}".encode("utf-8")
        ).decode("ascii")
        headers["Authorization"] = f"Basic {basic}"
    else:
        form["client_id"] = data["client_id"]

    body = urllib.parse.urlencode(form).encode("utf-8")
    req = urllib.request.Request(
        SSO_TOKEN_URL, data=body, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            tokens = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise TokenError(f"Refresh failed HTTP {e.code}: {err}") from e

    data["access_token"] = tokens["access_token"]
    if tokens.get("refresh_token"):
        data["refresh_token"] = tokens["refresh_token"]
    data["expires_at"] = int(time.time()) + int(tokens.get("expires_in", 1199)) - 30
    data["updated_at"] = int(time.time())
    return data


def ensure_token(char_id: str | None = None, force: bool = False) -> dict:
    """Ensure a valid access token exists for a character. Refreshes if needed.

    *char_id* selects the character (defaults to the store's primary, then the
    first bound character). Returns that character's credentials dict with a
    guaranteed-valid ``access_token`` — compatible with callers that read
    ``character_id`` / ``access_token`` from the result.

    Raises TokenError if no credentials are found or refresh fails.
    """
    store = load_store()
    cid, slot = get_char(store, char_id)
    if slot is None:
        raise TokenError("No credentials found. Run bind_sso.py first.")
    if not slot.get("refresh_token") and not slot.get("access_token"):
        raise TokenError("No credentials for this character. Run bind_sso.py.")
    expires_at = int(slot.get("expires_at") or 0)
    is_primary = cid == store.get("primary_character_id")
    if force or not slot.get("access_token") or time.time() >= expires_at:
        slot = _refresh_token(slot)
        store["characters"][cid] = slot
        save_store(store)
        if is_primary:
            sync_env_for_char(slot)
    else:
        # Keep process env in sync for this character
        os.environ["EVE_TOKEN_MAIN"] = str(slot["access_token"])
        if slot.get("character_id"):
            os.environ["EVE_CHAR_ID"] = str(slot["character_id"])
    return slot


# ---------------------------------------------------------------------------
# Core ESI HTTP request
# ---------------------------------------------------------------------------


def esi_request(
    endpoint: str,
    token: str | None = None,
    method: str = "GET",
    body: str | None = None,
    page: int | None = None,
    *,
    auto_token: bool = False,
    max_retries: int = 3,
    retry_statuses: tuple[int, ...] = (420, 502, 503, 504),
) -> tuple[dict | list | str, dict]:
    """Make a single ESI API request.

    Args:
        endpoint: ESI path, e.g. ``/characters/123/wallet/``
        token: Bearer token. Required unless *auto_token* is True.
        method: HTTP method (GET, POST, PUT, DELETE).
        body: JSON body for POST/PUT requests.
        page: Page number for paginated endpoints.
        auto_token: If True, automatically fetch/refresh token from credentials.
        max_retries: Max retry attempts for transient errors.
        retry_statuses: HTTP status codes eligible for retry.

    Returns:
        Tuple of (parsed_response_body, response_headers).

    Raises:
        TokenError: No token and auto_token is False, or refresh failed.
        ESIHTTPError: Non-retryable HTTP error.
        RateLimitError: HTTP 420 after exhausting retries.
    """
    if token is None and auto_token:
        creds = ensure_token()
        token = creds["access_token"]

    if token is None:
        raise TokenError("No token provided and auto_token=False")

    # Strip whitespace from token (fixes Windows piping issues)
    token = token.strip()

    url = f"{BASE_URL}{endpoint}"
    sep = "&" if "?" in url else "?"
    if page is not None:
        url += f"{sep}page={page}"

    headers: dict[str, str] = {
        "Authorization": f"Bearer {token}",
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = body.encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    # Retry loop for transient errors
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                resp_headers = {k.lower(): v for k, v in resp.getheaders()}
                raw = resp.read().decode("utf-8")
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = raw
                return parsed, resp_headers

        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            resp_headers = {k.lower(): v for k, v in e.headers.items()}

            # Auto-refresh on 401
            if e.code == 401 and auto_token:
                try:
                    creds = ensure_token(force=True)
                    new_token = creds["access_token"].strip()
                    # Rebuild request with new token
                    headers["Authorization"] = f"Bearer {new_token}"
                    req = urllib.request.Request(
                        url, data=data, headers=headers, method=method
                    )
                    # Retry once with new token (don't count against max_retries)
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        resp_headers = {k.lower(): v for k, v in resp.getheaders()}
                        raw = resp.read().decode("utf-8")
                        try:
                            parsed = json.loads(raw)
                        except json.JSONDecodeError:
                            parsed = raw
                        return parsed, resp_headers
                except TokenError:
                    raise
                except urllib.error.HTTPError as e2:
                    error_body = e2.read().decode("utf-8", errors="replace")
                    resp_headers = {k.lower(): v for k, v in e2.headers.items()}
                    raise ESIHTTPError(e2.code, error_body, resp_headers)

            # Rate limited (420)
            if e.code == 420:
                if attempt < max_retries:
                    wait = int(
                        resp_headers.get("x-esi-error-limit-reset", "60") or "60"
                    )
                    print(
                        f"Rate limited (420). Waiting {wait}s... (attempt {attempt + 1}/{max_retries})",
                        file=sys.stderr,
                    )
                    time.sleep(wait)
                    continue
                raise RateLimitError(420, error_body, resp_headers)

            # Transient server errors (502, 503, 504)
            if e.code in retry_statuses and attempt < max_retries:
                wait = 2**attempt  # exponential backoff: 1, 2, 4
                print(
                    f"HTTP {e.code}. Retrying in {wait}s... (attempt {attempt + 1}/{max_retries})",
                    file=sys.stderr,
                )
                time.sleep(wait)
                continue

            # Non-retryable error
            raise ESIHTTPError(e.code, error_body, resp_headers)


def esi_request_all_pages(
    endpoint: str,
    token: str | None = None,
    *,
    auto_token: bool = False,
    max_retries: int = 3,
) -> list:
    """Fetch all pages of a paginated ESI GET endpoint.

    Returns a flat list of all items across all pages.
    """
    first_page, headers = esi_request(
        endpoint, token, page=1, auto_token=auto_token, max_retries=max_retries
    )
    total_pages = int(headers.get("x-pages", "1"))
    if not isinstance(first_page, list):
        return [first_page]

    all_results = list(first_page)
    for p in range(2, total_pages + 1):
        page_data, _ = esi_request(
            endpoint, token, page=p, auto_token=auto_token, max_retries=max_retries
        )
        if isinstance(page_data, list):
            all_results.extend(page_data)
        print(
            f"  Page {p}/{total_pages} fetched ({len(page_data)} items)",
            file=sys.stderr,
        )
    return all_results


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def format_isk(amount: float | int | str) -> str:
    """Format ISK amount with thousands separator and suffix (K/M/B/T).

    >>> format_isk(868158906.17)
    '868.16M'
    >>> format_isk(1500)
    '1.5K'
    >>> format_isk(42.5)
    '42.50'
    >>> format_isk(1200000000000)
    '1.20T'
    """
    v = float(amount)
    if abs(v) >= 1_000_000_000_000:
        return f"{v / 1_000_000_000_000:.2f}T"
    if abs(v) >= 1_000_000_000:
        return f"{v / 1_000_000_000:.2f}B"
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:.2f}M"
    if abs(v) >= 1_000:
        return f"{v / 1_000:.1f}K"
    return f"{v:,.2f}"


def format_isk_full(amount: float | int | str) -> str:
    """Format ISK amount with thousands separator, no suffix.

    >>> format_isk_full(868158906.17)
    '868,158,906.17'
    """
    return f"{float(amount):,.2f}"


def format_datetime(esi_timestamp: str) -> str:
    """Convert an ESI ISO timestamp to local readable time.

    ESI timestamps look like ``"2025-01-15T14:30:00Z"``.
    Uses UTC offset to avoid encoding issues with non-ASCII timezone names.
    """
    dt = datetime.fromisoformat(esi_timestamp.replace("Z", "+00:00"))
    local = dt.astimezone()
    # Use numeric UTC offset instead of %Z which may produce non-ASCII
    return local.strftime("%Y-%m-%d %H:%M") + f" (UTC{local.strftime('%z')})"


def format_duration(seconds: float) -> str:
    """Format a duration in seconds to a human-readable string.

    >>> format_duration(90061)
    '1d 1h 1m'
    >>> format_duration(3661)
    '1h 1m'
    >>> format_duration(61)
    '1m 1s'
    """
    seconds = int(seconds)
    if seconds < 0:
        seconds = 0
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs and not days:  # Show seconds only if < 1 day
        parts.append(f"{secs}s")
    return " ".join(parts) if parts else "0s"


# ---------------------------------------------------------------------------
# Name resolution
# ---------------------------------------------------------------------------

_name_cache: dict[int, str] = {}


def resolve_names(
    type_ids: list[int],
    token: str | None = None,
    *,
    auto_token: bool = False,
) -> dict[int, str]:
    """Bulk resolve type/entity IDs to names via POST /universe/names/.

    Up to 1000 IDs per request. Results are cached in-process.

    Returns:
        Dict mapping ID -> name. IDs that could not be resolved are omitted.
    """
    # Filter out cached IDs and IDs that exceed int32 range
    # (structure IDs > 2^31-1 are not accepted by /universe/names/)
    INT32_MAX = 2_147_483_647
    uncached = [i for i in type_ids if i not in _name_cache and i <= INT32_MAX]
    result = {i: _name_cache[i] for i in type_ids if i in _name_cache}

    if not uncached:
        return result

    # Batch in chunks of 1000
    for offset in range(0, len(uncached), 1000):
        chunk = uncached[offset : offset + 1000]
        try:
            body_json = json.dumps(chunk)
            resp, _ = esi_request(
                "/universe/names/",
                token=token,
                method="POST",
                body=body_json,
                auto_token=auto_token,
            )
            if isinstance(resp, list):
                for item in resp:
                    if isinstance(item, dict) and "id" in item and "name" in item:
                        _name_cache[item["id"]] = item["name"]
                        result[item["id"]] = item["name"]
        except ESIHTTPError:
            # Batch failed — try smaller chunks of 100, then fall back to individual
            resolved_in_chunk = False
            for sub_offset in range(0, len(chunk), 100):
                sub_chunk = chunk[sub_offset : sub_offset + 100]
                try:
                    resp, _ = esi_request(
                        "/universe/names/",
                        token=token,
                        method="POST",
                        body=json.dumps(sub_chunk),
                        auto_token=auto_token,
                    )
                    if isinstance(resp, list):
                        for item in resp:
                            if isinstance(item, dict) and "id" in item and "name" in item:
                                _name_cache[item["id"]] = item["name"]
                                result[item["id"]] = item["name"]
                        resolved_in_chunk = True
                except ESIHTTPError:
                    # Even smaller chunk failed, resolve individually
                    for item_id in sub_chunk:
                        try:
                            item_resp, _ = esi_request(
                                f"/universe/types/{item_id}/",
                                token=token,
                                auto_token=auto_token,
                            )
                            if isinstance(item_resp, dict) and "name" in item_resp:
                                _name_cache[item_id] = item_resp["name"]
                                result[item_id] = item_resp["name"]
                        except ESIHTTPError:
                            pass

    return result


def resolve_type(
    type_id: int,
    token: str | None = None,
    *,
    auto_token: bool = False,
) -> str:
    """Resolve a single type ID to its name. Returns the ID as string on failure."""
    if type_id in _name_cache:
        return _name_cache[type_id]

    try:
        resp, _ = esi_request(
            f"/universe/types/{type_id}/",
            token=token,
            auto_token=auto_token,
        )
        if isinstance(resp, dict) and "name" in resp:
            _name_cache[type_id] = resp["name"]
            return resp["name"]
    except ESIHTTPError:
        pass
    return str(type_id)


def clear_name_cache() -> None:
    """Clear the in-process name cache."""
    _name_cache.clear()
