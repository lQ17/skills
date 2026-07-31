---
name: eve-esi
description: "Query and manage EVE Online characters via the ESI (EVE Swagger Interface) REST API. Use when the user asks about EVE Online character data, wallet balance, ISK transactions, assets, skill queue, skill points, clone locations, implants, fittings, contracts, market orders, mail, industry jobs, killmails, planetary interaction, loyalty points, or any other EVE account management task."
primary_credential: EVE_REFRESH_MAIN
env:
  - name: EVE_CLIENT_ID
    description: "EVE Developer Application Client ID (from https://developers.eveonline.com/applications)"
    required: true
    sensitive: false
  - name: EVE_TOKEN_MAIN
    description: "ESI OAuth2 access token for the main character. Expires after ~20 minutes."
    required: true
    sensitive: true
  - name: EVE_REFRESH_MAIN
    description: "ESI OAuth2 refresh token for automatic access token renewal."
    required: true
    sensitive: true
  - name: TELEGRAM_BOT_TOKEN
    description: "Telegram Bot API token for sending alerts and reports."
    required: false
    sensitive: true
  - name: TELEGRAM_CHAT_ID
    description: "Telegram chat ID where notifications are sent."
    required: false
    sensitive: false
  - name: DISCORD_WEBHOOK_URL
    description: "Discord webhook URL for sending alerts and reports."
    required: false
    sensitive: true
---

# Data Handling

This skill communicates exclusively with the official EVE Online ESI API (`esi.evetech.net`) and EVE SSO (`login.eveonline.com`).
No character data is exfiltrated to third-party servers.
Optional integrations (Telegram, Discord) are user-configured via environment variables and only transmit alerts defined by the user.

# EVE Online ESI

The ESI (EVE Swagger Interface) is the official REST API for EVE Online third-party development.

- Base URL: `https://esi.evetech.net/latest`
- Spec: `https://esi.evetech.net/latest/swagger.json`
- API Explorer: <https://developers.eveonline.com/api-explorer>

## Quick Start

After running `bind_sso.py` once to authorize your character, use these convenience scripts:

```bash
# Check your ISK balance (formatted)
python scripts/wallet_journal.py

# Character status (online, location, ship, clones, implants)
python scripts/status.py

# Skill queue overview
python scripts/skills.py

# Detailed skill queue + attributes
python scripts/skills.py --queue

# Search for a trained skill
python scripts/skills.py --search "mining"

# Asset summary by location
python scripts/assets.py

# Search for a specific item in your assets
python scripts/assets.py --search "raven"

# Filter assets by location
python scripts/assets.py --location "jita"

# Active industry jobs
python scripts/industry.py

# All industry jobs including completed
python scripts/industry.py --all

# Raw JSON output (for any script)
python scripts/status.py --json
python scripts/skills.py --json
python scripts/assets.py --json
python scripts/industry.py --json
```

For ad-hoc queries not covered by convenience scripts:

```bash
# Auto-token mode (recommended — auto-refreshes expired tokens)
python scripts/esi_query.py --auto-token --endpoint "/characters/{char_id}/wallet/"

# Endpoint supports {char_id} placeholder with --auto-token
python scripts/esi_query.py --auto-token --endpoint "/characters/{char_id}/skills/" --pretty

# Explicit token mode (still supported)
python scripts/esi_query.py --token "$TOKEN" --endpoint "/characters/12345/wallet/" --pretty
```

> **Windows note:** Use `--auto-token` to avoid whitespace issues that can occur when piping tokens on Windows.

## Authentication

ESI uses OAuth 2.0 via EVE SSO. Most character endpoints require an access token with the correct scope.

Quick flow:
1. Register an app at <https://developers.eveonline.com/applications>
2. Redirect user to SSO authorize URL with required scopes
3. Exchange the auth code for access + refresh tokens
4. Pass `Authorization: Bearer <TOKEN>` on every ESI request

For full details (PKCE, token refresh, scope list): see [references/authentication.md](references/authentication.md).

### Initial setup (bind_sso.py)

```bash
# Full scopes (recommended)
python scripts/bind_sso.py --client-id YOUR_CLIENT_ID --client-secret YOUR_SECRET

# Wallet scope only
python scripts/bind_sso.py --client-id YOUR_CLIENT_ID --scopes wallet

# Print URL instead of opening browser
python scripts/bind_sso.py --client-id YOUR_CLIENT_ID --no-browser
```

### Token management (ensure_token.py)

```bash
# Check/refresh token
python scripts/ensure_token.py

# Force refresh
python scripts/ensure_token.py --force

# Print token only (for piping)
python scripts/ensure_token.py --print-token

# JSON output
python scripts/ensure_token.py --json
```

### Multi-character support

Credentials are stored in a **per-character dictionary** at
`%USERPROFILE%\.eve-esi\credentials.json`:

```json
{
  "primary_character_id": "2124400030",
  "characters": {
    "2124400030": { "character_name": "gitignoreXD", "access_token": "...", "refresh_token": "...", "...": "..." },
    "另一个ID":     { "character_name": "altPilot",   "access_token": "...", "refresh_token": "...", "...": "..." }
  }
}
```

Legacy flat (single-character) files are migrated automatically on first load —
the old fields are preserved inside a new slot keyed by the character ID.

**Bind additional characters.** Re-running `bind_sso.py` *adds* a character; it
never deletes previously bound ones. The first bound character (or any run with
`--primary`) becomes the primary, whose credentials are mirrored into the Windows
`EVE_*` environment variables so existing dashboard configs (`$ENV:EVE_TOKEN_MAIN`,
etc.) keep working.

```bash
# Bind a second character (keeps gitignoreXD intact)
python scripts/bind_sso.py --client-id YOUR_CLIENT_ID

# Bind and force it to be the primary
python scripts/bind_sso.py --client-id YOUR_CLIENT_ID --primary
```

**Select a character per command.** Every script accepts `--char <ID>`; omitting
it uses the primary.

```bash
# List all bound characters and token status
python scripts/ensure_token.py --list

# Refresh + print token for a specific character
python scripts/ensure_token.py --char 2124400030 --print-token

# Wallet for a specific character
python scripts/wallet_journal.py --char 另一个ID

# Query any endpoint for a character from the store (no manual token needed)
python scripts/esi_query.py --char 2124400030 --endpoint "/characters/{char_id}/skills/" --pretty
```

## Convenience Scripts

### wallet_journal.py — Wallet balance and transactions

```bash
python scripts/wallet_journal.py                  # Balance (formatted)
python scripts/wallet_journal.py --what balance   # Balance only
python scripts/wallet_journal.py --what journal   # Recent journal entries
python scripts/wallet_journal.py --what journal --pages  # All journal pages
python scripts/wallet_journal.py --what transactions     # Wallet transactions
python scripts/wallet_journal.py --what all       # Everything
python scripts/wallet_journal.py --json           # Raw JSON output
```

### status.py — Character status overview

```bash
python scripts/status.py                     # Full overview (online, location, ship, clones, implants)
python scripts/status.py --section location  # Current location only
python scripts/status.py --section ship      # Current ship only
python scripts/status.py --section clones    # Jump clones only
python scripts/status.py --section implants  # Active implants only
python scripts/status.py --json              # Raw JSON output
```

### skills.py — Skill information

```bash
python scripts/skills.py                    # Summary + active queue
python scripts/skills.py --queue            # Full skill queue with status
python scripts/skills.py --search "mining"  # Search trained skills
python scripts/skills.py --json             # Raw JSON output
```

### assets.py — Asset overview

```bash
python scripts/assets.py                    # Top locations summary
python scripts/assets.py --summary          # Full location breakdown
python scripts/assets.py --search "raven"   # Find items by name
python scripts/assets.py --location "jita"  # Filter by location name
python scripts/assets.py --json             # Raw JSON output (all assets)
```

### industry.py — Industry jobs

```bash
python scripts/industry.py                  # Active jobs only
python scripts/industry.py --all            # Active + completed jobs
python scripts/industry.py --completed      # Completed jobs only
python scripts/industry.py --json           # Raw JSON output
```

### trade_roi.py — 交易 ROI 快速计算（含销量，默认吉他 Jita）

面向"两边挂单倒卖"模型：`单件利润 = S×(1−SF−ST) − B×(1+BF)`；默认费率 = Maybe Master 当前值
（BF=1.8% SF=1.8% ST=4.2%），可参数覆盖。输出毛价差 / 单件利润 / ROI / 总利润 /
近7日日均成交量 / 日利润潜力(件利×量) / 判定，并按日利润潜力排序。

```bash
python scripts/trade_roi.py "Power Circuit"                 # 按名字（精确/自动II↔2变体）
python scripts/trade_roi.py berserker                       # 模糊（内置清单前缀/包含）
python scripts/trade_roi.py --id 25617 3841 2478            # 按 type_id，可多个
python scripts/trade_roi.py "Power Circuit" --qty 100       # 指定数量算总利润
python scripts/trade_roi.py --bf 1.8 --sf 1.8 --st 4.2 "A"  # 自定义费率
python scripts/trade_roi.py --region 10000002 "A"           # 指定区域
python scripts/trade_roi.py --min-roi 5 -- "A" "B"          # 只看 ROI>=5%
python scripts/trade_roi.py --sort roi "A" "B"              # 按 ROI 排序
python scripts/trade_roi.py --json "A"                      # 机器可读输出
python scripts/trade_roi.py --list                          # 内置常用物品（模糊匹配用）
```

注意：只使用 ESI 公开接口，无需登录；若盘口倒挂（毛价差为负）说明买价高于卖价，
标准挂单模型必亏（多为操纵/闪崩盘口），脚本会如实标"亏损"。

## Public endpoints (no auth)

```bash
# Character public info
curl -s "https://esi.evetech.net/latest/characters/2114794365/" | python -m json.tool

# Portrait URLs
curl -s "https://esi.evetech.net/latest/characters/2114794365/portrait/"

# Corporation history
curl -s "https://esi.evetech.net/latest/characters/2114794365/corporationhistory/"

# Bulk affiliation lookup
curl -s -X POST "https://esi.evetech.net/latest/characters/affiliation/" \
  -H "Content-Type: application/json" \
  -d '[2114794365, 95538921]'
```

## Character info (authenticated)

```bash
TOKEN="<your_access_token>"
CHAR_ID="<your_character_id>"

# Online status (scope: esi-location.read_online.v1)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://esi.evetech.net/latest/characters/$CHAR_ID/online/"
```

## Wallet

```bash
# Balance (scope: esi-wallet.read_character_wallet.v1)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://esi.evetech.net/latest/characters/$CHAR_ID/wallet/"

# Journal (paginated)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://esi.evetech.net/latest/characters/$CHAR_ID/wallet/journal/?page=1"

# Transactions
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://esi.evetech.net/latest/characters/$CHAR_ID/wallet/transactions/"
```

## Assets

```bash
# All assets (paginated; scope: esi-assets.read_assets.v1)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://esi.evetech.net/latest/characters/$CHAR_ID/assets/?page=1"

# Resolve item locations
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '[1234567890, 9876543210]' \
  "https://esi.evetech.net/latest/characters/$CHAR_ID/assets/locations/"

# Resolve item names
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '[1234567890]' \
  "https://esi.evetech.net/latest/characters/$CHAR_ID/assets/names/"
```

## Skills

```bash
# All trained skills + total SP (scope: esi-skills.read_skills.v1)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://esi.evetech.net/latest/characters/$CHAR_ID/skills/"

# Skill queue (scope: esi-skills.read_skillqueue.v1)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://esi.evetech.net/latest/characters/$CHAR_ID/skillqueue/"

# Attributes (intelligence, memory, etc.)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://esi.evetech.net/latest/characters/$CHAR_ID/attributes/"
```

## Location and ship

```bash
# Current location (scope: esi-location.read_location.v1)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://esi.evetech.net/latest/characters/$CHAR_ID/location/"

# Current ship (scope: esi-location.read_ship_type.v1)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://esi.evetech.net/latest/characters/$CHAR_ID/ship/"
```

## Clones and implants

```bash
# Jump clones + home station (scope: esi-clones.read_clones.v1)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://esi.evetech.net/latest/characters/$CHAR_ID/clones/"

# Active implants (scope: esi-clones.read_implants.v1)
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://esi.evetech.net/latest/characters/$CHAR_ID/implants/"
```

## More endpoints

For contracts, fittings, mail, industry, killmails, market orders, mining, planetary interaction, loyalty points, notifications, blueprints, standings, and all other character endpoints, see [references/endpoints.md](references/endpoints.md).

## Dashboard Config

The skill supports a modular dashboard config for alerts, reports, and market tracking. Each user defines what they need in a JSON config file.

- **Schema**: [config/schema.json](config/schema.json) — full JSON Schema with all fields, types, and defaults
- **Example**: [config/example-config.json](config/example-config.json) — ready-to-use template

### Features

| Module | Description |
|--------|-------------|
| **Alerts** | Real-time polling for war decs, structure attacks, skill completions, wallet changes, industry jobs, PI extractors, killmails, contracts, clone jumps, mail |
| **Reports** | Cron-scheduled summaries: net worth, skill queue, industry, market orders, wallet, assets |
| **Market** | Price tracking with absolute thresholds and trend detection |

### Security

Tokens should **not** be stored in plain text. Use environment variable references:

```json
{
  "token": "$ENV:EVE_TOKEN_MAIN",
  "refresh_token": "$ENV:EVE_REFRESH_MAIN"
}
```

The config file should live outside the workspace (e.g. `~/.openclaw/eve-dashboard-config.json`).

### Validate a config

```bash
python scripts/validate_config.py path/to/config.json

# Show example config
python scripts/validate_config.py --example

# Show JSON schema
python scripts/validate_config.py --schema
```

## Using the query script

A reusable Python script is bundled at `scripts/esi_query.py`. It handles pagination, auto-refresh, and retry logic.

```bash
# Auto-token mode (recommended — auto-refreshes expired tokens):
python scripts/esi_query.py --auto-token --endpoint "/characters/{char_id}/wallet/"

# The {char_id} placeholder is auto-replaced with your character ID when using --auto-token
python scripts/esi_query.py --auto-token --endpoint "/characters/{char_id}/skills/" --pretty

# Fetch all pages of assets
python scripts/esi_query.py --auto-token --endpoint "/characters/{char_id}/assets/" --pages --pretty

# POST request (e.g. asset names)
python scripts/esi_query.py --auto-token --endpoint "/characters/{char_id}/assets/names/" \
  --method POST --body '[1234567890]' --pretty

# Explicit token mode (still supported, but --auto-token is preferred):
python scripts/esi_query.py --token "$TOKEN" --endpoint "/characters/12345/wallet/" --pretty
```

> **Windows note:** On Windows, piping tokens can introduce trailing whitespace causing 404 errors. Use `--auto-token` to avoid this issue entirely.

## Best practices

- **Caching**: respect the `Expires` header; do not poll before it expires.
- **Error limits**: monitor `X-ESI-Error-Limit-Remain`; back off when low.
- **User-Agent**: always set a descriptive User-Agent with contact info.
- **Rate limits**: some endpoints (mail, contracts) have internal rate limits returning HTTP 520.
- **Pagination**: check the `X-Pages` response header; iterate with `?page=N`.
- **Versioning**: use `/latest/` for current stable routes. `/dev/` may change without notice.

## Resolving type IDs

ESI returns numeric type IDs (e.g. for ships, items, skills). Resolve names via:

```bash
# Single type
curl -s "https://esi.evetech.net/latest/universe/types/587/"

# Bulk names (up to 1000 IDs)
curl -s -X POST "https://esi.evetech.net/latest/universe/names/" \
  -H "Content-Type: application/json" \
  -d '[587, 638, 11393]'
```

## ⚠️ MANDATORY: Always resolve IDs to names — NEVER guess

ESI endpoints return numeric IDs for skills, ships, items, types, locations, corporations, alliances, and many other entities. **You MUST NOT guess or assume what an ID maps to.** Always resolve IDs to their actual names before presenting results to the user.

**Rules:**

1. **Never fabricate a name for an ID.** If an ESI response contains only a numeric ID (e.g. `skill_id: 13278`, `type_id: 587`, `system_id: 30000815`), you must resolve it before telling the user what it is.
2. **Use the resolution endpoints.** Call `/universe/types/{id}/` for a single type, or `/universe/names/` (POST with an ID array) for bulk resolution. For skills specifically, use `scripts/skills.py --search "<name>"` or the non-JSON `--queue` mode which already resolves names.
3. **Apply to ALL ID types**, including but not limited to: `skill_id`, `type_id`, `system_id`, `station_id`, `corporation_id`, `alliance_id`, `constellation_id`, `region_id`, `ship_type_id`, `item_id`, `race_id`, `bloodline_id`, `faction_id`.
4. **If resolution fails** (network error, 404, etc.), display the raw ID and explicitly state that the name could not be resolved — do not substitute a guess.

**Example of what NOT to do:**
```
skill_id 13278 → "Caldari Battleship V"  ❌ (guessed wrong!)
```

**What to do instead:**
```
# Resolve via ESI
curl -s "https://esi.evetech.net/latest/universe/types/13278/" | python -m json.tool
# → "name": "Archaeology"
skill_id 13278 → "Archaeology V"  ✅
```
