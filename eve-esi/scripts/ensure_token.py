#!/usr/bin/env python3
"""Ensure a valid EVE access token (refresh if needed).

Reads credentials from (in order):
  1) %USERPROFILE%\\.eve-esi\\credentials.json
  2) environment variables EVE_* 

Updates both the credentials file and Windows User env vars.

Usage:
  python ensure_token.py
  python ensure_token.py --print-token   # print access token only
  python ensure_token.py --force        # force refresh
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SSO_TOKEN = "https://login.eveonline.com/v2/oauth/token"
USER_AGENT = "Grok-EVE-ESI-Bind/1.0 (local agent; contact via local machine)"


def cred_path() -> Path:
    return Path.home() / ".eve-esi" / "credentials.json"


def load_creds() -> dict:
    path = cred_path()
    data: dict = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    # Env overrides / fills
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
    path = cred_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Don't drop secret if present
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
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


def refresh(data: dict) -> dict:
    if not data.get("client_id") or not data.get("refresh_token"):
        raise SystemExit(
            "Missing client_id or refresh_token. Run bind_sso.py first."
        )
    form = {
        "grant_type": "refresh_token",
        "refresh_token": data["refresh_token"],
    }
    headers = {
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
    req = urllib.request.Request(SSO_TOKEN, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            tokens = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Refresh failed HTTP {e.code}: {err}") from e

    data["access_token"] = tokens["access_token"]
    if tokens.get("refresh_token"):
        data["refresh_token"] = tokens["refresh_token"]
    data["expires_at"] = int(time.time()) + int(tokens.get("expires_in", 1199)) - 30
    data["updated_at"] = int(time.time())
    save_creds(data)
    return data


def ensure(force: bool = False) -> dict:
    data = load_creds()
    if not data.get("refresh_token") and not data.get("access_token"):
        raise SystemExit("No credentials found. Run bind_sso.py first.")
    expires_at = int(data.get("expires_at") or 0)
    if force or not data.get("access_token") or time.time() >= expires_at:
        data = refresh(data)
    else:
        # keep env in sync for this process
        os.environ["EVE_TOKEN_MAIN"] = str(data["access_token"])
        if data.get("character_id"):
            os.environ["EVE_CHAR_ID"] = str(data["character_id"])
    return data


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
    data = ensure(force=args.force)
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
