#!/usr/bin/env python3
"""EVE SSO bind helper (PKCE + optional client secret).

Binds a character for local agents:
  - exchanges OAuth code for access/refresh tokens
  - writes Windows User environment variables (any agent can read after restart)
  - writes %USERPROFILE%\\.eve-esi\\credentials.json as backup

Usage:
  python bind_sso.py --client-id YOUR_CLIENT_ID
  python bind_sso.py --client-id YOUR_CLIENT_ID --client-secret YOUR_SECRET
  python bind_sso.py --client-id YOUR_CLIENT_ID --scopes wallet   # wallet only
  python bind_sso.py --client-id YOUR_CLIENT_ID --port 8765
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

SSO_AUTHORIZE = "https://login.eveonline.com/v2/oauth/authorize"
SSO_TOKEN = "https://login.eveonline.com/v2/oauth/token"
SSO_VERIFY = "https://login.eveonline.com/oauth/verify"
USER_AGENT = "Grok-EVE-ESI-Bind/1.0 (local agent; contact via local machine)"

# Broad default set so agents can query common personal data without re-auth.
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


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    return verifier, challenge


def cred_dir() -> Path:
    p = Path.home() / ".eve-esi"
    p.mkdir(parents=True, exist_ok=True)
    return p


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

def http_form(url: str, data: dict, headers: dict | None = None) -> dict:
    body = urllib.parse.urlencode(data).encode("utf-8")
    hdrs = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": USER_AGENT,
        "Host": "login.eveonline.com",
    }
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Token request failed HTTP {e.code}: {err}") from e


def verify_token(access_token: str) -> dict:
    req = urllib.request.Request(
        SSO_VERIFY,
        headers={
            "Authorization": f"Bearer {access_token}",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    result: dict | None = None
    expected_state: str = ""

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in ("/callback", "/"):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return
        qs = urllib.parse.parse_qs(parsed.query)
        if "error" in qs:
            msg = qs.get("error_description", qs["error"])[0]
            self._html(400, f"Authorization failed: {msg}")
            CallbackHandler.result = {"error": msg}
            return
        code = qs.get("code", [None])[0]
        state = qs.get("state", [None])[0]
        if not code or state != CallbackHandler.expected_state:
            self._html(400, "Invalid code/state. Close this tab and retry.")
            CallbackHandler.result = {"error": "invalid_state_or_code"}
            return
        CallbackHandler.result = {"code": code, "state": state}
        self._html(
            200,
            "Authorization successful. You can close this tab and return to the agent.",
        )

    def _html(self, status: int, message: str) -> None:
        body = f"""<!doctype html><html><head><meta charset="utf-8">
<title>EVE ESI Bind</title></head><body style="font-family:sans-serif;padding:2rem">
<h1>EVE ESI</h1><p>{message}</p></body></html>""".encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def wait_for_code(port: int, state: str, timeout: int = 300) -> str:
    CallbackHandler.result = None
    CallbackHandler.expected_state = state
    server = http.server.HTTPServer(("127.0.0.1", port), CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Listening for callback on http://127.0.0.1:{port}/callback ...", flush=True)
    start = time.time()
    try:
        while time.time() - start < timeout:
            if CallbackHandler.result is not None:
                if "error" in CallbackHandler.result:
                    raise SystemExit(f"SSO error: {CallbackHandler.result['error']}")
                return CallbackHandler.result["code"]
            time.sleep(0.2)
        raise SystemExit("Timed out waiting for browser authorization.")
    finally:
        server.shutdown()


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def save_credentials(payload: dict) -> Path:
    path = cred_dir() / "credentials.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    # Best-effort restrict on Windows
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Bind EVE Online character via SSO")
    parser.add_argument("--client-id", required=True, help="EVE application Client ID")
    parser.add_argument(
        "--client-secret",
        default=os.environ.get("EVE_CLIENT_SECRET", ""),
        help="Optional Client Secret (confidential app)",
    )
    parser.add_argument("--port", type=int, default=8765, help="Local callback port")
    parser.add_argument(
        "--scopes",
        default="default",
        help="Preset name (default|wallet) or space-separated scope list",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open browser; print URL only",
    )
    args = parser.parse_args()

    if not port_free(args.port):
        raise SystemExit(
            f"Port {args.port} is in use. Close the process or pass --port <other>."
        )

    if args.scopes in SCOPE_PRESETS:
        scopes = SCOPE_PRESETS[args.scopes]
    else:
        scopes = args.scopes.split()

    redirect_uri = f"http://localhost:{args.port}/callback"
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(24)

    params = {
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "client_id": args.client_id,
        "scope": " ".join(scopes),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = SSO_AUTHORIZE + "/?" + urllib.parse.urlencode(params)

    print("=" * 60)
    print("EVE SSO Bind")
    print("=" * 60)
    print(f"Callback URL (must match your app exactly):\n  {redirect_uri}")
    print(f"Scopes ({len(scopes)}):")
    for s in scopes:
        print(f"  - {s}")
    print()
    print("Open this URL if the browser does not open:")
    print(auth_url)
    print()

    if not args.no_browser:
        webbrowser.open(auth_url)

    code = wait_for_code(args.port, state)

    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": verifier,
    }
    headers = {}
    if args.client_secret:
        # Confidential client: Basic auth only (do not also send client_id in body)
        basic = base64.b64encode(
            f"{args.client_id}:{args.client_secret}".encode("utf-8")
        ).decode("ascii")
        headers["Authorization"] = f"Basic {basic}"
    else:
        # Public client (PKCE): client_id in body, no secret
        token_data["client_id"] = args.client_id

    tokens = http_form(SSO_TOKEN, token_data, headers)
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]
    expires_in = int(tokens.get("expires_in", 1199))

    verify = verify_token(access)
    char_id = str(verify.get("CharacterID") or verify.get("character_id") or "")
    char_name = verify.get("CharacterName") or verify.get("name") or ""
    granted = verify.get("Scopes") or verify.get("scp") or ""

    # Persist for any agent
    set_windows_user_env("EVE_CLIENT_ID", args.client_id)
    if args.client_secret:
        set_windows_user_env("EVE_CLIENT_SECRET", args.client_secret)
    set_windows_user_env("EVE_TOKEN_MAIN", access)
    set_windows_user_env("EVE_REFRESH_MAIN", refresh)
    if char_id:
        set_windows_user_env("EVE_CHAR_ID", char_id)
    if char_name:
        set_windows_user_env("EVE_CHAR_NAME", char_name)

    expires_at = int(time.time()) + expires_in - 30
    payload = {
        "client_id": args.client_id,
        "has_client_secret": bool(args.client_secret),
        "character_id": int(char_id) if char_id.isdigit() else char_id,
        "character_name": char_name,
        "scopes": scopes,
        "granted_scopes": granted,
        "access_token": access,
        "refresh_token": refresh,
        "expires_at": expires_at,
        "updated_at": int(time.time()),
        "redirect_uri": redirect_uri,
    }
    # Store secret only if provided
    if args.client_secret:
        payload["client_secret"] = args.client_secret

    path = save_credentials(payload)

    print()
    print("Bind successful.")
    print(f"  Character : {char_name} ({char_id})")
    print(f"  Cred file : {path}")
    print("  User env  : EVE_CLIENT_ID, EVE_TOKEN_MAIN, EVE_REFRESH_MAIN, EVE_CHAR_ID")
    print()
    print("Note: already-open terminals/agents may not see new User env vars")
    print("until restarted. This process and the credentials file work immediately.")
    print()
    print("Next: query wallet journal with:")
    print(
        f'  python ensure_token.py && python esi_query.py --token "%EVE_TOKEN_MAIN%" '
        f'--endpoint "/characters/{char_id}/wallet/journal/" --pages --pretty'
    )


if __name__ == "__main__":
    main()

