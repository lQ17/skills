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
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

# Allow importing the shared module next to this file
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    SSO_AUTHORIZE_URL,
    SSO_TOKEN_URL,
    SSO_VERIFY_URL,
    USER_AGENT,
    DEFAULT_SCOPES,
    SCOPE_PRESETS,
    WALLET_SCOPES,
    set_windows_user_env,
    add_character,
    cred_path,
)


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    return verifier, challenge


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
        SSO_VERIFY_URL,
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
    parser.add_argument(
        "--primary",
        action="store_true",
        help="Make this character the primary (mirrors into Windows env vars)",
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
    auth_url = SSO_AUTHORIZE_URL + "/?" + urllib.parse.urlencode(params)

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
    headers: dict[str, str] = {}
    if args.client_secret:
        # Confidential client: Basic auth only (do not also send client_id in body)
        basic = base64.b64encode(
            f"{args.client_id}:{args.client_secret}".encode("utf-8")
        ).decode("ascii")
        headers["Authorization"] = f"Basic {basic}"
    else:
        # Public client (PKCE): client_id in body, no secret
        token_data["client_id"] = args.client_id

    tokens = http_form(SSO_TOKEN_URL, token_data, headers)
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]
    expires_in = int(tokens.get("expires_in", 1199))

    verify = verify_token(access)
    char_id = str(verify.get("CharacterID") or verify.get("character_id") or "")
    char_name = verify.get("CharacterName") or verify.get("name") or ""
    granted = verify.get("Scopes") or verify.get("scp") or ""

    # App-level client id is single-valued; always mirror it into the env.
    set_windows_user_env("EVE_CLIENT_ID", args.client_id)
    if args.client_secret:
        set_windows_user_env("EVE_CLIENT_SECRET", args.client_secret)

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

    # Write into the multi-character store (does NOT delete other characters)
    store = add_character(payload, set_primary=args.primary)
    is_primary = store["primary_character_id"] == char_id

    print()
    print("Bind successful.")
    print(f"  Character : {char_name} ({char_id})" + ("  [PRIMARY]" if is_primary else ""))
    print(f"  Cred file : {cred_path()}")
    print(f"  Bound characters ({len(store['characters'])}):")
    for cid, c in store["characters"].items():
        mark = " <- primary" if cid == store["primary_character_id"] else ""
        print(f"    - {c.get('character_name', '?')} ({cid}){mark}")
    print()
    print("Note: already-open terminals/agents may not see new User env vars")
    print("until restarted. This process and the credentials file work immediately.")
    print()
    print("Next: list characters with:")
    print("  python ensure_token.py --list")
    print("Or query this character with:")
    print(
        f'  python esi_query.py --auto-token --char {char_id} '
        f'--endpoint "/characters/{char_id}/wallet/journal/" --pages --pretty'
    )


if __name__ == "__main__":
    main()
