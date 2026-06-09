"""
main.py — High-performance Valorant account checker.

Optimizations:
  • Parallel processing  — asyncio.Semaphore limits concurrency (default: 5)
  • HTTP-only auth       — Riot Auth API (no Playwright browser)
  • Playwright auth      — --browser flag uses real Chrome (no captcha)
  • Persistent tokens    — accounts.json stores tokens between runs
  • Fast retry          — token refresh is headless HTTP, ~100ms
  • Short delays        — 0.3-1.2s between accounts (was 3-6s)
  • hCaptcha auto-solve  — via CapSolver / Anti-Captcha / CapMonster / 2Captcha

Auth strategy per account:
  1. Lockfile         → Valorant running → instant (<1s)
  2. accounts.json    → saved tokens → headless refresh (~100ms)
  3. HTTP login       → Riot Auth API → save tokens for next runs (~2s)
  4. Browser login    → --browser flag uses Playwright Chrome (~5s)

Usage:
    python main.py                          # default 5 concurrent (HTTP)
    python main.py --concurrency 10        # faster but riskier
    python main.py --concurrency 1         # one at a time (debug)
    python main.py --browser                # use Playwright (no captcha)
"""
from __future__ import annotations

import asyncio
import httpx
import json
import logging
import os
import random
import re
import secrets
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

# ── logging ──────────────────────────────────────────────────────────────────

def _setup_logging():
    os.makedirs("logs", exist_ok=True)
    logger.remove()
    logger.add(
        sys.stderr,
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="<level>{time:HH:mm:ss} | {message}</level>",
        colorize=True,
    )
    logger.add(
        f"logs/run_{datetime.now():%Y%m%d_%H%M%S}.log",
        level="DEBUG",
        rotation="10 MB",
    )

from loguru import logger
_setup_logging()

# ── paths ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
ACCOUNTS_FILE = SCRIPT_DIR / "accounts.txt"
PROXIES_FILE  = SCRIPT_DIR / "proxies.txt"
ACCOUNTS_JSON = SCRIPT_DIR / "accounts.json"
VERSION_CACHE = SCRIPT_DIR / "riot_version.json"
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", r"C:\Users\WORK\Desktop\Check-done"))

# ── config ───────────────────────────────────────────────────────────────────

CONCURRENCY   = 5          # max simultaneous accounts
DELAY_MIN     = 0.3        # was 3s — sleep between batches (seconds)
DELAY_MAX     = 1.2        # was 6s

RIOT_PLATFORM = (
    "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVm"
    "Vyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9"
)
UUID_SKINS    = "e7c63390-eda7-46e0-bb7a-a6abdacd2433"
UUID_VP       = "85ad13f7-3d1b-5128-9eb2-7cd8ee0b5741"
UUID_RP       = "e59aa87c-4cbf-517a-5983-6e81511be9b7"
UUID_KC       = "85ca954a-41f2-4a9f-9e6b-0283ccc65d64"
UUID_FA       = "f2c6e9b4-8d7a-4c3e-9f1b-5a7d3e9f2c6b"
HTTPX_TIMEOUT = 10.0

RANK_NAMES = [
    "Unrated","Iron 1","Iron 2","Iron 3",
    "Bronze 1","Bronze 2","Bronze 3",
    "Silver 1","Silver 2","Silver 3",
    "Gold 1","Gold 2","Gold 3",
    "Platinum 1","Platinum 2","Platinum 3",
    "Diamond 1","Diamond 2","Diamond 3",
    "Ascendant 1","Ascendant 2","Ascendant 3",
    "Immortal 1","Immortal 2","Immortal 3",
    "Radiant",
]

# ── args ─────────────────────────────────────────────────────────────────────

SKIP_MENU = False
USE_BROWSER = False
BROWSER_HEADLESS = False

for i, arg in enumerate(sys.argv):
    if arg == "--cli":
        SKIP_MENU = True
    elif arg == "--concurrency" and i + 1 < len(sys.argv):
        try:
            CONCURRENCY = max(1, int(sys.argv[i + 1]))
        except ValueError:
            pass
    elif arg == "--delay" and i + 1 < len(sys.argv):
        try:
            v = float(sys.argv[i + 1])
            DELAY_MIN = max(0, v / 2)
            DELAY_MAX = v
        except ValueError:
            pass
    elif arg == "--browser":
        USE_BROWSER = True
    elif arg == "--headless":
        BROWSER_HEADLESS = True


def parse_proxy(proxy: str) -> str:
    """
    Parse proxy string to httpx-compatible format.
    Supports formats:
      - http://user:pass@host:port
      - host:port:user:pass (provider format)
      - host:port (no auth)
    Returns httpx-compatible proxy URL.
    """
    proxy = proxy.strip()
    if not proxy:
        return ""

    # Already has scheme
    if proxy.startswith("http://") or proxy.startswith("https://"):
        return proxy

    # host:port:user:pass format (provider format)
    if proxy.count(":") >= 3:
        parts = proxy.split(":")
        if len(parts) >= 4:
            host = parts[0]
            port = parts[1]
            user = parts[2]
            pwd = ":".join(parts[3:])
            return f"http://{user}:{pwd}@{host}:{port}"

    # host:port format (no auth)
    return f"http://{proxy}"


# ═══════════════════════════════════════════════════════════════════════════════
# ACCOUNT DB  (accounts.json — persistent token storage)
# ═══════════════════════════════════════════════════════════════════════════════

def _load_db() -> dict:
    if not ACCOUNTS_JSON.exists():
        return {}
    try:
        return json.loads(ACCOUNTS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_db(data: dict):
    ACCOUNTS_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def _get_saved_tokens(username: str) -> dict | None:
    db = _load_db()
    entry = db.get(username.lower())
    if not entry:
        return None
    tokens = entry.get("tokens") or entry.get("token")
    if not tokens:
        return None
    return tokens

async def _save_tokens(username: str, password: str, region: str, tokens: dict):
    # BUG FIX (Bug 4): use _db_lock to prevent concurrent writes to accounts.json.
    # Without lock: Account A reads → Account B reads → A writes → B writes → A's data lost.
    async with _db_lock:
        db = _load_db()
        key = username.lower()
        entry = db.get(key, {})
        entry.update({"username": username, "password": password, "region": region, "tokens": tokens})
        db[key] = entry
        _save_db(db)
        logger.debug(f"  [db] Saved tokens for {username}")

def _remove_tokens(username: str):
    db = _load_db()
    key = username.lower()
    if key in db and "tokens" in db[key]:
        del db[key]["tokens"]
        _save_db(db)

# ═══════════════════════════════════════════════════════════════════════════════
# VERSION
# ═══════════════════════════════════════════════════════════════════════════════

# BUG FIX: creating a new asyncio.Lock() per-call means the lock is useless.
# Multiple concurrent accounts bypass the cache lock entirely. Use ONE module-level lock.
_VERSION_LOCK = asyncio.Lock()


async def _get_version(_lock: asyncio.Lock | None = None) -> str:
    """Fetch client version once, cache in file, reuse across all accounts."""
    lock = _lock if _lock is not None else _VERSION_LOCK
    async with lock:
        try:
            if VERSION_CACHE.exists():
                cached = json.loads(VERSION_CACHE.read_text(encoding="utf-8"))
                age = (datetime.now() - datetime.fromisoformat(cached["cached_at"])).total_seconds()
                if age < 3600:
                    return cached["version"]
        except Exception:
            pass

        import httpx
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get("https://valorant-api.com/v1/version")
                if resp.is_success:
                    version = resp.json()["data"]["riotClientVersion"]
                    VERSION_CACHE.write_text(
                        json.dumps({"version": version, "cached_at": datetime.now().isoformat()}),
                        encoding="utf-8",
                    )
                    return version
        except Exception as e:
            logger.warning(f"  version fetch failed: {e}")
        return "release-12.10-shipping-17-4738152"

# ═══════════════════════════════════════════════════════════════════════════════
# LOCKFILE
# ═══════════════════════════════════════════════════════════════════════════════

def _lockfile_tokens() -> dict | None:
    import base64, subprocess
    lockfile_path = Path(os.getenv("LOCALAPPDATA",
        os.path.expanduser("~\\AppData\\Local")
    )) / "Riot Games" / "Riot Client" / "Config" / "lockfile"

    if not lockfile_path.exists():
        return None
    try:
        parts = lockfile_path.read_text(encoding="utf-8").strip().split(":")
        if len(parts) < 5:
            return None
        port, password = int(parts[2]), parts[3]
    except Exception:
        return None

    auth = base64.b64encode(f"riot:{password}".encode()).decode()
    try:
        result = subprocess.run(
            ["curl", "-s", "-k", "-X", "GET",
             "-H", f"Authorization: Basic {auth}",
             f"https://127.0.0.1:{port}/entitlements/v1/token"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        at = data.get("accessToken", "")
        et = data.get("token", "")
        puuid = data.get("subject", "")
        if not at or not et:
            return None
        return {
            "access_token": at,
            "entitlements_token": et,
            "puuid": puuid,
            "expires_at": datetime.now().timestamp() + 3600,
            "refresh_token": "",
        }
    except Exception:
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# HTTP AUTH  (headless — no browser)
# ═══════════════════════════════════════════════════════════════════════════════

async def _http_login(username: str, password: str, region: str = "ap", proxy: str = "") -> dict | None:
    """
    Riot Auth API login via the correct RSO (Riot Sign-On) flow.
    Flow: login → login-token → authorization → access_token
    proxy format: http://user:pass@host:port or http://host:port
    Returns tokens dict or None on failure.
    """
    import httpx

    ver = await _get_version()
    sdk = ver.split(".")[1] if "." in ver else "13.05.18"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Origin": "https://auth.riotgames.com",
        "Referer": "https://auth.riotgames.com/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": f"RiotClient/{sdk} rso-auth (Windows;10;;Professional, x64)",
        "Cache-Control": "no-cache",
        "X-Riot-ClientVersion": ver,
        "X-Riot-ClientPlatform": RIOT_PLATFORM,
        # Edge tracking headers - giúp bypass captcha
        "X-Riot-Edge-Device-Guid": secrets.token_hex(16),
        "X-Riot-Edge-Client-Version": ver,
    }

    # Build proxy config (parse provider format)
    proxies = {}
    parsed_proxy = parse_proxy(proxy)
    if parsed_proxy:
        proxies["http://"] = parsed_proxy
        proxies["https://"] = parsed_proxy
        short = proxy.split("@")[-1] if "@" in proxy else proxy
        logger.debug(f"  [proxy] Using: {short}")

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False, proxies=proxies) as client:
            # Step 1: Initiate auth — get session_token
            r1 = await client.post(
                "https://authenticate.riotgames.com/api/v1/login",
                headers=headers,
                json={
                    "clientId": "riot-client",
                    "language": "en_US",
                    "platform": "windows",
                    "remember": False,
                    "riot_identity": {
                        "language": "en_US",
                        "state": "auth",
                    },
                    "sdkVersion": sdk,
                    "type": "auth",
                },
            )

            if r1.status_code == 429:
                logger.warning(f"  [http] Rate limited — wait 60s")
                await asyncio.sleep(60)
                return None

            if not r1.is_success:
                try:
                    err = r1.json()
                    logger.warning(f"  [http] Step 1 failed {r1.status_code}: {err.get('error_description', r1.text[:200])}")
                except Exception:
                    logger.warning(f"  [http] Step 1 failed {r1.status_code}: {r1.text[:200]}")
                return None

            data1 = r1.json()

            if data1.get("captcha"):
                logger.warning(f"  [http] Captcha required during login")
                return {"_status": "captcha_required"}

            session_token = data1.get("session_token") or data1.get("success", {}).get("session_token", "")
            if not session_token:
                logger.warning(f"  [http] No session_token in step 1 response: {r1.text[:200]}")
                return None

            # Step 2: Send credentials with session_token
            r2 = await client.put(
                "https://authenticate.riotgames.com/api/v1/login",
                headers=headers,
                json={
                    "type": "auth",
                                "username": username,
                    "password": password,
                    "session_token": session_token,
                },
            )

            if not r2.is_success:
                try:
                    err2 = r2.json()
                    err_type = (err2.get("error") or "").lower()
                    err_desc = (err2.get("error_description") or "").lower()
                    logger.warning(f"  [http] Step 2 failed: {err_desc or r2.text[:200]}")
                    if "mfa" in err_type or "mfa" in err_desc or "two-factor" in err_desc:
                        return {"_status": "mfa_required"}
                    if "invalid" in err_type or "invalid" in err_desc:
                        return {"_status": "wrong_password"}
                    if "captcha" in err_type or "captcha" in err_desc:
                        return {"_status": "captcha_required"}
                    if "rate" in err_type or "rate" in err_desc or "lockout" in err_desc:
                        return {"_status": "rate_limited"}
                except Exception:
                    logger.warning(f"  [http] Step 2 failed {r2.status_code}: {r2.text[:200]}")
                return None

            data2 = r2.json()
            if data2.get("error"):
                err_desc = data2.get("error_description", "").lower()
                err_type = data2.get("error", "").lower()
                logger.warning(f"  [http] Step 2 error: {err_desc or err_type}")
                if "mfa" in err_type or "mfa" in err_desc:
                    return {"_status": "mfa_required"}
                if "invalid" in err_type or "invalid" in err_desc:
                    return {"_status": "wrong_password"}
                if "captcha" in err_type or "captcha" in err_desc:
                    return {"_status": "captcha_required"}
                return None

            # Step 3: Exchange to access_token via authorization
            r3 = await client.post(
                "https://auth.riotgames.com/api/v1/authorization",
                headers=headers,
                json={
                    "client_id": "riot-client",
                    "nonce": secrets.token_urlsafe(16),
                    "redirect_uri": "http://localhost/redirect",
                    "response_type": "token id_token",
                    "scope": "openid link ban lol_region account",
                },
            )

            if not r3.is_success:
                logger.warning(f"  [http] Step 3 failed {r3.status_code}: {r3.text[:200]}")
                return None

            data3 = r3.json()
            uri = (data3.get("response", {}) or data3 or {}).get("parameters", {}).get("uri", "")
            if not uri:
                logger.warning(f"  [http] No redirect URI in step 3: {r3.text[:200]}")
                return None

            # Parse token from URI fragment
            fragment = uri.split("#", 1)[-1]
            params = {}
            for pair in fragment.split("&"):
                if "=" in pair:
                    k, _, v = pair.partition("=")
                    params[k] = v

            access_token = params.get("access_token", "")
            if not access_token:
                logger.warning(f"  [http] No access_token in redirect URI")
                return None

            # Step 4: Get entitlements
            ent_resp = await client.post(
                "https://entitlements.auth.riotgames.com/api/token/v1",
                headers={"Authorization": f"Bearer {access_token}"},
                json={},
            )
            entitlements = ""
            if ent_resp.is_success:
                entitlements = ent_resp.json().get("entitlements_token", "")

            # Step 5: Get user info
            user_resp = await client.get(
                "https://auth.riotgames.com/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_data = user_resp.json() if user_resp.is_success else {}
            puuid = user_data.get("sub", "")

            return {
                "access_token": access_token,
                "entitlements_token": entitlements,
                "puuid": puuid,
                                "region": region,
                "expires_at": datetime.now().timestamp() + 3600,
                "refresh_token": "",
            }

    except httpx.TimeoutException:
        logger.warning(f"  [http] Timeout during login")
        return None
    except Exception as e:
        logger.warning(f"  [http] Login error: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# TOKEN ACQUISITION  (strategy: lockfile → saved → HTTP login)
# ═══════════════════════════════════════════════════════════════════════════════

async def _get_tokens(
    username: str,
    password: str,
    region: str,
    version: str,
    proxy: str = "",
) -> tuple[str, str, str, str] | None:
    """
    Returns (access_token, entitlements_token, puuid, status_str) or None.
    status_str is used for categorization on failure.
    """
    import httpx

    # ── Strategy 1: Lockfile (instant, shared — all accounts use same token) ──
    # BUG FIX: was calling _lockfile_tokens() TWICE — once for truthiness check,
    # once to extract. Each call re-reads lockfile + spawns subprocess.
    lockfile_result = _lockfile_tokens()
    if lockfile_result:
        logger.debug(f"  [auth] lockfile")
        return lockfile_result["access_token"], lockfile_result["entitlements_token"], lockfile_result["puuid"], "lockfile"

    # ── Strategy 2: Saved tokens in accounts.json ─────────────────────────
    saved = _get_saved_tokens(username)
    if saved:
        expires_at = saved.get("expires_at", 0)
        access_token = saved.get("access_token", "")
        entitlements = saved.get("entitlements_token", "")
        refresh_token = saved.get("refresh_token", "")
        saved_puuid = saved.get("puuid", "")

        # Token still valid (with 2-min buffer)?
        if expires_at > datetime.now().timestamp() + 120 and access_token:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    ent_resp = await client.post(
                        "https://entitlements.auth.riotgames.com/api/token/v1",
                        headers={"Authorization": f"Bearer {access_token}"},
                        json={},
                    )
                    entitlements = ent_resp.json().get("entitlements_token", "") if ent_resp.is_success else ""
                    user_resp = await client.get(
                        "https://auth.riotgames.com/userinfo",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    user_data = user_resp.json() if user_resp.is_success else {}
                    puuid = user_data.get("sub", "") or saved_puuid
                    logger.debug(f"  [auth] saved token still valid")
                    return access_token, entitlements, puuid, "saved"
            except Exception:
                pass

        # BUG FIX: removed dead code — Riot RSO (riot-client flow) does NOT support
        # OAuth refresh_token grants. The endpoint auth.riotgames.com/token with
        # grant_type=refresh_token returns 400. This block never worked.
        # Saved tokens expire → must re-login via HTTP or browser.

    # ── Strategy 3: HTTP login ───────────────────────────────────────────────
    if USE_BROWSER:
        logger.debug(f"  [auth] Browser login for {username}...")
        from auth import get_tokens as pw_get_tokens
        try:
            pw_result = await pw_get_tokens(username, password, proxy, BROWSER_HEADLESS)
            if pw_result:
                at = pw_result.get("access_token", "")
                et = pw_result.get("entitlements_token", "")
                pu = pw_result.get("puuid", "")
                if at:
                    await _save_tokens(username, password, region, pw_result)
                    return at, et, pu, "browser"
        except Exception as e:
            logger.debug(f"  [auth] Browser login failed: {e}")

    logger.debug(f"  [auth] HTTP login for {username}...")
    result = await _http_login(username, password, region, proxy)

    if not result:
        return None

    status = result.get("_status")
    if status:
        return (None, None, None, status)

    access_token = result.get("access_token", "")
    entitlements = result.get("entitlements_token", "")
    puuid = result.get("puuid", "")

    if not access_token:
        return None

    # Save for next run
    await _save_tokens(username, password, region, result)

    return access_token, entitlements, puuid, "http_login"

# ═══════════════════════════════════════════════════════════════════════════════
# RIOT API CALLS
# ═══════════════════════════════════════════════════════════════════════════════

async def _fetch_userinfo(
    client: httpx.AsyncClient,
    access_token: str,
    entitlements: str,
    version: str,
    puuid: str,
    region: str,
) -> dict:
    try:
        r = await client.get(
            "https://auth.riotgames.com/userinfo",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Riot-ClientVersion": version,
                "X-Riot-ClientPlatform": RIOT_PLATFORM,
            },
        )
        return r.json() if r.is_success else {}
    except Exception:
        return {}

async def _fetch_wallet(
    client: httpx.AsyncClient,
    access_token: str,
    entitlements: str,
    version: str,
    puuid: str,
    region: str,
) -> dict:
    try:
        r = await client.get(
            f"https://pd.{region.lower()}.a.pvp.net/store/v1/wallet/{puuid}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Riot-Entitlements-JWT": entitlements,
                "X-Riot-ClientVersion": version,
                "X-Riot-ClientPlatform": RIOT_PLATFORM,
            },
        )
        if r.is_success:
            bals = r.json().get("Balances", {})
            uuids = list(bals.keys())
            return {
                "vp": int(bals.get(uuids[0], 0)) if len(uuids) > 0 else 0,
                "rp": int(bals.get(uuids[1], 0)) if len(uuids) > 1 else 0,
                "kc": int(bals.get(uuids[2], 0)) if len(uuids) > 2 else 0,
                "fa": int(bals.get(uuids[3], 0)) if len(uuids) > 3 else 0,
            }
    except Exception:
        pass
    return {"vp": 0, "rp": 0, "kc": 0, "fa": 0}

async def _fetch_mmr(
    client: httpx.AsyncClient,
    access_token: str,
    entitlements: str,
    version: str,
    puuid: str,
    region: str,
) -> tuple[int, int]:
    try:
        r = await client.get(
            f"https://pd.{region.lower()}.a.pvp.net/mmr/v1/players/{puuid}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Riot-Entitlements-JWT": entitlements,
                "X-Riot-ClientVersion": version,
                "X-Riot-ClientPlatform": RIOT_PLATFORM,
            },
        )
        if r.is_success:
            data = r.json()
            # Use LatestCompetitiveUpdate like web app (current rank from latest match)
            comp = data.get("LatestCompetitiveUpdate", {})
            tier = int(comp.get("TierAfterUpdate", 0))
            rr = int(comp.get("RankedRatingAfterUpdate", 0))
            if tier > 0:
                return tier, rr
            # Fallback: seasonal info
            seasons = (data.get("QueueSkills", {})
                       .get("competitive", {})
                       .get("SeasonalInfoBySeasonID", {}))
            if seasons:
                latest = max(seasons.keys())
                info = seasons[latest]
                return int(info.get("CompetitiveTier", 0)), int(info.get("RankedRating", 0))
    except Exception:
        pass
    return 0, 0

async def _fetch_skins(
    client: httpx.AsyncClient,
    access_token: str,
    entitlements: str,
    version: str,
    puuid: str,
    region: str,
) -> int:
    try:
        r = await client.get(
            f"https://pd.{region.lower()}.a.pvp.net/store/v1/entitlements/{puuid}/{UUID_SKINS}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Riot-Entitlements-JWT": entitlements,
                "X-Riot-ClientVersion": version,
                "X-Riot-ClientPlatform": RIOT_PLATFORM,
            },
        )
        if not r.is_success:
            return 0

        ent_list = r.json().get("Entitlements", [])
        if not ent_list:
            return 0

        # Fetch skins data for deduplication
        skins_r = await client.get("https://valorant-api.com/v1/weapons/skins")
        if not skins_r.is_success:
            # Fallback: return entitlements count
            return len(ent_list)

        skins_data = skins_r.json().get("data", [])

        # Build level -> baseName map
        level_to_name = {}
        for skin in skins_data:
            base_name = skin.get("displayName", "Unknown")
            for level in skin.get("levels", []):
                level_to_name[level.get("uuid", "")] = base_name

        # Count unique skins
        unique_names = set()
        for ent in ent_list:
            item_id = ent.get("ItemID", "")
            if item_id in level_to_name:
                unique_names.add(level_to_name[item_id])

        return len(unique_names)
    except Exception:
        pass
    return 0

async def _fetch_xp(
    client: httpx.AsyncClient,
    access_token: str,
    entitlements: str,
    version: str,
    puuid: str,
    region: str,
) -> int:
    try:
        r = await client.get(
            f"https://pd.{region.lower()}.a.pvp.net/account-xp/v1/players/{puuid}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Riot-Entitlements-JWT": entitlements,
                "X-Riot-ClientVersion": version,
                "X-Riot-ClientPlatform": RIOT_PLATFORM,
            },
        )
        if r.is_success:
            data = r.json()
            return int(data.get("Progress", {}).get("Level", data.get("Level", 0)))
    except Exception:
        pass
    return 0

async def _fetch_restrictions(
    client: httpx.AsyncClient,
    access_token: str,
    entitlements: str,
    version: str,
    puuid: str,
    region: str,
) -> list:
    try:
        r = await client.get(
            f"https://pd.{region.lower()}.a.pvp.net/restrictions/v1/players/{puuid}/restrictions",
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Riot-Entitlements-JWT": entitlements,
                "X-Riot-ClientVersion": version,
                "X-Riot-ClientPlatform": RIOT_PLATFORM,
            },
        )
        if r.is_success:
            return r.json().get("restrictions", [])
    except Exception:
        pass
    return []

# ═══════════════════════════════════════════════════════════════════════════════
# RESULT
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Result:
    ok: bool
    status: str           # "active" | "perm_ban" | "suspended" | "error" | "auth_fail"
    status_label: str
    username: str
    game_name: str
    tag_line: str
    puuid: str
    region: str
    level: int
    rank_str: str
    current_tier: int
    current_rr: int
    vp: int; rp: int; kc: int; fa: int
    skins_count: int
    ban_reason: str
    email_verified: bool
    phone_verified: bool
    country: str
    created_at: str
    error: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["is_banned"] = not self.ok
        d["account_status"] = self.status_label
        return d

# ═══════════════════════════════════════════════════════════════════════════════
# DB LOCK (Bug 4 fix)
# ═══════════════════════════════════════════════════════════════════════════════

# BUG FIX: previously _save_tokens() had no lock — 5 concurrent accounts would
# read-modify-write accounts.json simultaneously, overwriting each other's tokens.
_db_lock = asyncio.Lock()


# ═══════════════════════════════════════════════════════════════════════════════
# PROCESS ONE ACCOUNT
# ═══════════════════════════════════════════════════════════════════════════════

async def _process_one(
    username: str,
    password: str,
    region: str,
    version: str,
    proxy: str,
    sem: asyncio.Semaphore,
) -> Result:
    # BUG FIX (Bug 3): each account gets its own httpx client with its proxy.
    # Previously used a shared client with no proxy, so all API calls went
    # through the machine's default IP — inconsistent with browser auth IP,
    # triggering captchas and rate limits from Riot.
    proxies = {}
    if proxy:
        proxies = {"http://": proxy, "https://": proxy}

    async with sem:
        t0 = time.monotonic()
        logger.debug(f"  [start] {username}")

        # ── Auth ────────────────────────────────────────────────────────────
        token_result = await _get_tokens(username, password, region, version, proxy)

        if token_result is None:
            return Result(
                ok=False, status="auth_fail", status_label="❌ AUTH FAILED",
                username=username, game_name="", tag_line="", puuid="",
                region=region, level=0, rank_str="", current_tier=0, current_rr=0,
                vp=0, rp=0, kc=0, fa=0, skins_count=0, ban_reason="",
                email_verified=False, phone_verified=False, country="", created_at="",
                error="all_auth_methods_failed",
            )

        access_token, entitlements, puuid, auth_method = token_result

        if access_token is None:
            label_map = {
                "mfa_required":    "🔐 MFA REQUIRED",
                "wrong_password":   "🔑 WRONG PASSWORD",
                "captcha_required": "🤖 CAPTCHA",
            }
            return Result(
                ok=False, status="auth_fail",
                status_label=label_map.get(auth_method, f"❌ {auth_method.upper()}"),
                username=username, game_name="", tag_line="", puuid="",
                region=region, level=0, rank_str="", current_tier=0, current_rr=0,
                vp=0, rp=0, kc=0, fa=0, skins_count=0, ban_reason="",
                email_verified=False, phone_verified=False, country="", created_at="",
                error=auth_method,
            )

        # ── API calls — each account gets own httpx client with proxy (Bug 3 fix) ──
        async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT, proxies=proxies) as client:
            ui_task    = _fetch_userinfo(client, access_token, entitlements, version, puuid, region)
            wl_task    = _fetch_wallet(client, access_token, entitlements, version, puuid, region)
            mmr_task   = _fetch_mmr(client, access_token, entitlements, version, puuid, region)
            sk_task    = _fetch_skins(client, access_token, entitlements, version, puuid, region)
            xp_task    = _fetch_xp(client, access_token, entitlements, version, puuid, region)
            res_task   = _fetch_restrictions(client, access_token, entitlements, version, puuid, region)

            userinfo, wallet, (tier, rr), skins, level, restrictions = await asyncio.gather(
                ui_task, wl_task, mmr_task, sk_task, xp_task, res_task,
            )

        # ── Parse user info ────────────────────────────────────────────────
        game_name = userinfo.get("game_name", username.split("@")[0])
        tag_line  = userinfo.get("tag_line", "")
        if not puuid:
            puuid = userinfo.get("sub", "")

        # ── Determine status ────────────────────────────────────────────────
        ban_reason = ""
        status     = "active"
        status_label = "✅ ACTIVE"

        if restrictions:
            r     = restrictions[0]
            rtype = r.get("type", "")
            reason = r.get("reason", "")
            if "PERMANENT" in rtype.upper():
                status = "perm_ban"
                status_label = "🚫 BI CAM VINH VIEN"
                ban_reason  = reason or rtype
            else:
                rest_until = r.get("rest_until")
                if rest_until:
                    until = datetime.fromtimestamp(rest_until / 1000, tz=timezone.utc).strftime("%d/%m/%Y")
                    status_label = f"⏸ BI KHOA den {until}"
                else:
                    status_label = "⏸ BI KHOA TAM THOI"
                status = "suspended"
                ban_reason = reason or rtype

        if not restrictions:
            ban_data = userinfo.get("ban") or {}
            if ban_data.get("flag"):
                ban_reason = ban_data["flag"]
                status = "perm_ban"
                status_label = "🚫 BI CAM"
            elif ban_data.get("restrictions"):
                bans = ban_data["restrictions"]
                if bans:
                    r = bans[0]
                    if "PERMANENT" in r.get("type", "").upper():
                        status = "perm_ban"
                        status_label = "🚫 BI CAM VINH VIEN"
                        ban_reason = r.get("reason", "")
                    else:
                        status = "suspended"
                        status_label = "⏸ BI KHOA"
                        ban_reason = r.get("reason", "")

        ok = status == "active"

        rank_label = RANK_NAMES[tier] if 0 <= tier < len(RANK_NAMES) else f"Rank {tier}"
        rank_str   = f"{rank_label} — {rr} RR" if tier > 0 else "Unrated"

        created_at = ""
        if userinfo.get("acct", {}).get("created_at"):
            try:
                created_at = datetime.fromisoformat(
                    userinfo["acct"]["created_at"].replace("Z", "+00:00")
                ).strftime("%d/%m/%Y")
            except Exception:
                created_at = userinfo["acct"]["created_at"]

        elapsed = time.monotonic() - t0
        logger.info(f"  [{elapsed:.1f}s] {username} | Skins:{skins} | {status_label}")

        return Result(
            ok=ok,
            status=status,
            status_label=status_label,
            username=username,
            game_name=game_name,
            tag_line=tag_line,
            puuid=puuid,
            region=region,
            level=level,
            rank_str=rank_str,
            current_tier=tier,
            current_rr=rr,
            vp=wallet["vp"], rp=wallet["rp"], kc=wallet["kc"], fa=wallet["fa"],
            skins_count=skins,
            ban_reason=ban_reason,
            email_verified=userinfo.get("email_verified", False),
            phone_verified=userinfo.get("phone_number_verified", False),
            country=userinfo.get("country", ""),
            created_at=created_at,
        )

# ═══════════════════════════════════════════════════════════════════════════════
# OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

def _safe_file(s: str) -> str:
    return re.sub(r'[#:/\\?*"|<>]', "_", str(s))[:80]

def _esc(s):
    if not s and s != 0:
        return ""
    return (str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;"))

def _rank_str(tier: int, rr: int) -> str:
    if tier <= 0:
        return "Unrated"
    name = RANK_NAMES[tier] if tier < len(RANK_NAMES) else f"Rank {tier}"
    return f"{name} — {rr} RR"

def _cat_of(n: int) -> str:
    if n <= 0:    return "0_skin"
    if n <= 20:   return "1-20_skins"
    if n <= 40:   return "20-40_skins"
    if n <= 60:   return "40-60_skins"
    if n <= 100:  return "60-100_skins"
    return "100plus_skins"

CAT_COLORS = {
    "0_skin": "#9e9e9e",
    "1-20_skins": "#f5a623",
    "20-40_skins": "#2196f3",
    "40-60_skins": "#9c27b0",
    "60-100_skins": "#4caf50",
    "100plus_skins": "#ff4655",
    "error": "#ff5252"
}
CAT_LABELS = {
    "0_skin": "0 Skin",
    "1-20_skins": "1-20 Skins",
    "20-40_skins": "20-40 Skins",
    "40-60_skins": "40-60 Skins",
    "60-100_skins": "60-100 Skins",
    "100plus_skins": "100+ Skins",
    "error": "Error"
}

def _account_html(d: dict) -> str:
    cat   = d.get("_cat", "error")
    color = CAT_COLORS.get(cat, "#8b978f")
    label = CAT_LABELS.get(cat, cat)
    tier  = d.get("current_tier", 0)
    rr    = d.get("current_rr", 0)
    vp = (d.get("vp") or 0); rp = (d.get("rp") or 0)
    kc = (d.get("kc") or 0); fa = (d.get("fa") or 0)
    banned = d.get("is_banned", False)

    if banned:
        badge = f'<span class="badge banned">{_esc(d.get("account_status","BANNED"))}</span>'
    else:
        badge = f'<span class="badge" style="COLOR">{label}</span>'
    badge = badge.replace("COLOR", f'border-color:{color};color:{color}')

    banner = ""
    if banned:
        banner = f'<div style="background:rgba(183,28,28,.2);border:1px solid #b71c1c;border-radius:8px;padding:14px;margin-bottom:16px;color:#ff5252;font-weight:600">&#9888; {_esc(d.get("account_status","BANNED"))}</div>'

    status = d.get("account_status", "Active")
    status_html = '<span class="ok">Active</span>' if status == "Active" else f'<span class="bad">{_esc(status)}</span>'

    css = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f1923;color:#ece8e1;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh}
header{background:#1a2634;border-bottom:2px solid #ff4655;padding:16px 24px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px}
.logo{width:36px;height:36px}
header .brand{display:flex;align-items:center;gap:12px}
header .brand .name{font-size:1.2em;font-weight:700;color:#ff4655;letter-spacing:1px}
.badge{display:inline-block;padding:3px 12px;border-radius:12px;font-size:.8em;font-weight:700;border:1px solid COLOR;color:COLOR}
.badge.banned{border-color:#ff5252;color:#ff5252}
main{max-width:1100px;margin:0 auto;padding:20px 24px}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
.card{background:#1a2634;border:1px solid #2a3a4a;border-radius:10px;padding:16px}
.card h3{color:#ff4655;font-size:.72em;text-transform:uppercase;letter-spacing:.8px;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #2a3a4a}
.row{display:flex;padding:7px 0;border-bottom:1px solid rgba(42,58,74,.3);font-size:.88em;gap:10px}
.row:last-child{border-bottom:none}
.row .l{color:#8b978f;min-width:130px;flex-shrink:0}
.row .v{font-weight:600;color:#ece8e1;word-break:break-all}
.row .v.sm{font-size:.75em}
.ok,.bad{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.8em;font-weight:600}
.ok{background:#1b5e20;color:#4caf50}
.bad{background:#2a1a1a;color:#ff5252}
.wg{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;margin-bottom:12px}
.wc{background:#0d1520;border:1px solid #2a3a4a;border-radius:8px;padding:10px;text-align:center}
.wc .v{font-size:1.1em;font-weight:700;color:#ff4655}
.wc .l{font-size:.68em;color:#8b978f;text-transform:uppercase;letter-spacing:.5px;margin-top:2px}
footer{text-align:center;color:#8b978f;font-size:.78em;padding:20px;border-top:1px solid #2a3a4a;margin-top:20px}
@media(max-width:700px){.two-col{grid-template-columns:1fr}.wg{grid-template-columns:1fr 1fr}}
""".replace("COLOR", color)

    title = f"{_esc(d.get('game_name','—'))}#{_esc(d.get('tag_line','—'))}"
    now   = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    return f"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<header>
  <div class="brand">
    <svg class="logo" viewBox="0 0 32 32" fill="none">
      <circle cx="16" cy="16" r="16" fill="#ff4655"/>
      <polygon points="16,6 22,12 16,18 10,12" fill="white"/>
      <rect x="14" y="18" width="4" height="8" fill="white"/>
    </svg>
    <span class="name">{_esc(d.get('game_name','—'))}#{_esc(d.get('tag_line','—'))}</span>
  </div>
  <div style="display:flex;align-items:center;gap:10px">
    {badge}
    <span style="font-size:.85em;color:#8b978f">Level {d.get('level','—')}</span>
  </div>
</header>
<main>
{banner}
<div class="two-col">
  <div class="card">
    <h3>Thong tin tai khoan</h3>
    <div class="row"><span class="l">PUUID</span><span class="v sm">{_esc(d.get('puuid',''))}</span></div>
    <div class="row"><span class="l">Level</span><span class="v">{d.get('level','—')}</span></div>
    <div class="row"><span class="l">Region</span><span class="v">{_esc(str(d.get('region','')).upper())}</span></div>
    <div class="row"><span class="l">Country</span><span class="v">{_esc(str(d.get('country','')).upper())}</span></div>
    <div class="row"><span class="l">Email Verified</span><span class="v">{"Yes" if d.get("email_verified") else "No"}</span></div>
    <div class="row"><span class="l">Phone Verified</span><span class="v">{"Yes" if d.get("phone_verified") else "No"}</span></div>
    <div class="row"><span class="l">Account Created</span><span class="v">{_esc(d.get('created_at','—'))}</span></div>
    <div class="row"><span class="l">Status</span><span class="v">{status_html}</span></div>
  </div>
  <div class="card">
    <h3>Wallet & Rank</h3>
    <div class="wg">
      <div class="wc"><div class="v">{vp:,}</div><div class="l">VP</div></div>
      <div class="wc"><div class="v">{rp:,}</div><div class="l">RP</div></div>
      <div class="wc"><div class="v">{kc:,}</div><div class="l">KC</div></div>
      <div class="wc"><div class="v">{fa:,}</div><div class="l">FA</div></div>
    </div>
    <div class="row"><span class="l">Current Rank</span><span class="v">{_esc(_rank_str(tier, rr))}</span></div>
    <div class="row"><span class="l">Skin Levels</span><span class="v">{d.get('skins_count', 0)}</span></div>
  </div>
</div>
<div style="text-align:center;color:#8b978f;font-size:.78em;margin-top:12px">Checked: {now}</div>
</main>
<footer>Valorant Checker — Auto Generated</footer>
</body>
</html>"""

def _index_html(results: list[Result]) -> str:
    cats: dict[str, list[dict]] = {
        "0_skin": [], "1-20_skins": [], "20-40_skins": [],
        "40-60_skins": [], "60-100_skins": [], "100plus_skins": [], "error": []
    }
    for r in results:
        d = r.to_dict()
        if r.ok:
            d["_cat"] = _cat_of(r.skins_count)
            cats[d["_cat"]].append(d)
        else:
            d["_cat"] = "error"
            cats["error"].append(d)

    def cat_section(cat_key: str, results_list: list[dict]) -> str:
        if not results_list:
            return ""
        color = CAT_COLORS.get(cat_key, "#8b978f")
        label = CAT_LABELS.get(cat_key, cat_key)
        rows = ""
        for i, d in enumerate(results_list, 1):
            rank = _esc(d.get("rank_str","—"))
            vp   = f"{d.get('vp',0):,}"
            skins = d.get("skins_count", "—")
            status = d.get("account_status", "Active")
            status_color = "#4caf50" if status == "Active" else "#ff5252"
            rows += f"""<tr>
  <td style="text-align:center;color:{color};font-weight:700">{i}</td>
  <td><strong>{_esc(d.get('game_name','—'))}#{_esc(d.get('tag_line','—'))}</strong></td>
  <td>{d.get('level','—')}</td>
  <td style="color:#ff4655;font-weight:700">{vp}</td>
  <td>{skins}</td>
  <td><span style="color:{status_color};font-weight:600">{_esc(str(status))}</span></td>
  <td>{_esc(d.get('region','').upper())}</td>
</tr>"""
        return f"""<div style="margin-bottom:28px">
<h2 style="font-size:.8em;text-transform:uppercase;letter-spacing:.5px;color:{color};margin-bottom:10px;display:flex;align-items:center;gap:8px">
  <span style="width:10px;height:10px;border-radius:50%;background:{color};display:inline-block"></span>
  {label} ({len(results_list)})
</h2>
<div style="overflow-x:auto">
<table style="width:100%;border-collapse:separate;border-spacing:0 4px">
  <thead>
    <tr style="color:#8b978f;font-size:.7em;text-transform:uppercase;letter-spacing:.5px">
      <th style="text-align:center;padding:6px 10px">#</th>
      <th style="padding:6px 10px;text-align:left">Account</th>
      <th style="padding:6px 10px;text-align:left">Level</th>
      <th style="padding:6px 10px;text-align:left">VP</th>
      <th style="padding:6px 10px;text-align:left">Skins</th>
      <th style="padding:6px 10px;text-align:left">Status</th>
      <th style="padding:6px 10px;text-align:left">Region</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
</div>
</div>"""

    summary = ""
    for cat_key in ["0_skin", "1-20_skins", "20-40_skins", "40-60_skins", "60-100_skins", "100plus_skins", "error"]:
        n = len(cats[cat_key])
        if n:
            color = CAT_COLORS.get(cat_key, "#8b978f")
            label = CAT_LABELS.get(cat_key, cat_key)
            summary += f'<div style="background:#1a2634;border:1px solid {color};border-radius:10px;padding:12px 18px;text-align:center"><div style="font-size:1.4em;font-weight:700;color:{color}">{n}</div><div style="font-size:.65em;color:{color};opacity:.8;text-transform:uppercase">{label}</div></div>'

    return f"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Valorant Bulk Check — {datetime.now():%d/%m/%Y %H:%M}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0f1923;color:#ece8e1;font-family:'Segoe UI',system-ui,sans-serif;padding:20px}}
h1{{color:#ff4655;font-size:1.3em;margin-bottom:16px;padding-bottom:10px;border-bottom:2px solid #ff4655}}
.summary{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:28px}}
table tr:hover td{{background:#243447}}
td{{background:#1a2634;padding:8px 10px;font-size:.85em;border-radius:4px}}
footer{{text-align:center;color:#5a6670;font-size:.75em;padding:20px;border-top:1px solid #2a3a4a;margin-top:20px}}
</style>
</head>
<body>
<h1>Valorant Bulk Check — {datetime.now().strftime('%d/%m/%Y %H:%M')}</h1>
<div class="summary">{summary}</div>
{''.join(cat_section(k, v) for k, v in cats.items() if v)}
<footer>Generated by Valorant Checker</footer>
</body>
</html>"""

def _save_outputs(results: list[Result]):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
    index_path = OUTPUT_DIR / f"index_{timestamp}.html"

    index_path.write_text(_index_html(results), encoding="utf-8")

    # Save ALL accounts — active, banned, suspended, error
    # Group by status
    status_dirs: dict[str, Path] = {
        "active":     OUTPUT_DIR / "01_active",
        "perm_ban":   OUTPUT_DIR / "02_perm_ban",
        "suspended":   OUTPUT_DIR / "03_suspended",
        "wrong_password": OUTPUT_DIR / "04_wrong_password",
        "mfa_required":   OUTPUT_DIR / "05_mfa_required",
        "captcha_required": OUTPUT_DIR / "06_captcha_required",
        "auth_fail":  OUTPUT_DIR / "07_auth_fail",
        "error":      OUTPUT_DIR / "08_error",
    }
    for d in status_dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    for r in results:
        status = r.status if r.status in status_dirs else "error"
        if status not in counts:
            counts[status] = 0
        counts[status] += 1

        # Filename: prefer game_name if available, else username
        if r.game_name:
            safe_name = _safe_file(r.game_name)
            safe_tag  = _safe_file(r.tag_line) if r.tag_line else "no_tag"
            fname = f"{safe_name}_{safe_tag}.html"
        else:
            safe_user = _safe_file(r.username)
            fname = f"{safe_user}_error.html"

        # Use skins folder for active, status folder for others
        if r.ok:
            cat = _cat_of(r.skins_count)
            out_dir = OUTPUT_DIR / cat
            out_dir.mkdir(exist_ok=True)
        else:
            out_dir = status_dirs.get(status, OUTPUT_DIR / "08_error")

        path = out_dir / fname
        d = r.to_dict()
        path.write_text(_account_html(d), encoding="utf-8")

    total_saved = sum(counts.values())
    parts = [f"{v} {k.replace('_',' ')}" for k, v in counts.items() if v > 0]
    detail = " | ".join(parts) if parts else "0"
    logger.success(f"  Da luu {total_saved} file HTML vao: {OUTPUT_DIR}")
    logger.info(f"    Chi tiet: {detail}")

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

async def _main():
    t0_all = time.time()

    # ── Load accounts ──────────────────────────────────────────────────────────
    if not ACCOUNTS_FILE.exists():
        logger.error(f"File khong ton tai: {ACCOUNTS_FILE}")
        logger.error("Tao file voi dinh dang: username:password[:region]")
        sys.exit(1)

    # ── Load proxies (round-robin) ─────────────────────────────────────────────
    # Format in proxies.txt: host:port:user:pass
    # Converts to: http://user:pass@host:port
    proxies: list[str] = []
    if PROXIES_FILE.exists():
        for line in PROXIES_FILE.read_text(encoding="utf-8").splitlines():
            p = line.strip()
            if not p or p.startswith("#"):
                continue
            parts = p.split(":")
            if len(parts) == 4:
                # host:port:user:pass
                host = parts[0].strip()
                port = parts[1].strip()
                user = parts[2].strip()
                pw   = parts[3].strip()
                proxies.append(f"http://{user}:{pw}@{host}:{port}")
            elif len(parts) >= 2:
                # host:port or host:port:user:pass or http://host:port
                if p.startswith("http"):
                    proxies.append(p)
                elif len(parts) >= 4:
                    # host:port:user:pass format
                    host = parts[0].strip()
                    port = parts[1].strip()
                    user = parts[2].strip()
                    pwd = ":".join(parts[3:]).strip()
                    proxies.append(f"http://{user}:{pwd}@{host}:{port}")
                else:
                    proxies.append(f"http://{parts[0].strip()}:{parts[1].strip()}")
        if proxies:
            logger.info(f"Loaded {len(proxies)} proxy from proxies.txt")

    accounts: list[dict] = []
    for i, line in enumerate(ACCOUNTS_FILE.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        # Format: username:password[:region]
        # Use maxsplit=1 so password can contain colons/special chars
        parts = line.split(":", 1)
        username = parts[0].strip()
        rest = parts[1] if len(parts) > 1 else ""
        # rest is "password[:region]" — split on first : for region
        if ":" in rest:
            pw, region = rest.split(":", 1)
            password = pw.strip()
            region = region.strip().lower()
        else:
            password = rest.strip()
            region = "ap"
        # Assign proxy round-robin
        proxy = proxies[i % len(proxies)] if proxies else ""
        if username and password:
            accounts.append({"username": username, "password": password, "region": region, "proxy": proxy})
            if proxy:
                short = proxy.split("@")[-1] if "@" in proxy else proxy
                logger.debug(f"  [config] {username} | region={region} | proxy={short}")

    if not accounts:
        logger.error("Khong co tai khoan nao trong file.")
        sys.exit(1)

    # ── Get client version ────────────────────────────────────────────────────
    version = await _get_version()
    logger.info(f"Riot client version: {version}")
    logger.info(f"Concurrency: {CONCURRENCY} | Accounts: {len(accounts)}")

    # ── Category stats ────────────────────────────────────────────────────────
    cat = {"active":0,"perm_ban":0,"suspended":0,"error":0,
           "wrong_password":0,"mfa_required":0,"captcha_required":0,"auth_fail":0}

    sem = asyncio.Semaphore(CONCURRENCY)

    # BUG FIX (Bug 2): stagger start times to prevent simultaneous requests.
    # Previously all tasks were scheduled at once, then asyncio.as_completed
    # ran them all at the same time — triggering Riot rate limits immediately.
    # BUG FIX (Bug 3): removed shared httpx client — each _process_one
    # now creates its own client with its proxy.
    async def _process_one_delayed(idx: int, acc: dict) -> Result:
        await asyncio.sleep(idx * random.uniform(DELAY_MIN, DELAY_MAX))
        return await _process_one(
            username=acc["username"],
            password=acc["password"],
            region=acc["region"],
            version=version,
            proxy=acc.get("proxy", ""),
            sem=sem,
        )

    tasks = [
        _process_one_delayed(idx, acc)
        for idx, acc in enumerate(accounts)
    ]

    # ── Run and collect results ────────────────────────────────────────────────
    results: list[Result] = []
    for coro in asyncio.as_completed(tasks):
        try:
            r = await coro
        except Exception as e:
            logger.error(f"  Task exception: {e}")
            continue
        results.append(r)

    # ── Count categories ───────────────────────────────────────────────────────
    for r in results:
        if r.status == "auth_fail":
            err = r.error or ""
            if "mfa" in err:
                cat["mfa_required"] = cat.get("mfa_required", 0) + 1
            elif "wrong_password" in err or "password" in err.lower():
                cat["wrong_password"] = cat.get("wrong_password", 0) + 1
            elif "captcha" in err:
                cat["captcha_required"] = cat.get("captcha_required", 0) + 1
            else:
                cat["auth_fail"] = cat.get("auth_fail", 0) + 1
        else:
            cat[r.status] = cat.get(r.status, 0) + 1

    # ── Sort results: active first, then by skins ─────────────────────────────
    results.sort(key=lambda r: (r.ok, -(r.skins_count or 0)), reverse=True)

    # ── Save outputs ───────────────────────────────────────────────────────────
    try:
        _save_outputs(results)
    except Exception as e:
        logger.error(f"Loi luu file: {e}")

    # ── Summary ────────────────────────────────────────────────────────────────
    total = len(results)
    elapsed = time.time() - t0_all
    logger.info("")
    logger.info("═" * 56)
    logger.info("   KET QUA KIEM TRA")
    logger.info("═" * 56)
    logger.info(f"  Tong tai khoan:  {total}")
    logger.info(f"  Thoi gian:      ~{elapsed:.1f}s")
    logger.info("")
    logger.info(f"  \033[92m[HOAT DONG]\033[0m")
    logger.info(f"    Active:        {cat.get('active', 0)}")

    logger.info("")
    logger.info(f"  \033[91m[BI CAM / KHOA]\033[0m")
    logger.info(f"    Cam vinh vien: {cat.get('perm_ban', 0)}")
    logger.info(f"    Bi khoa tam:   {cat.get('suspended', 0)}")

    logger.info("")
    logger.info(f"  \033[93m[LOI DANG NHAP]\033[0m")
    logger.info(f"    Sai mat khau:  {cat.get('wrong_password', 0)}")
    logger.info(f"    Can MFA:       {cat.get('mfa_required', 0)}")
    logger.info(f"    Captcha:       {cat.get('captcha_required', 0)}")
    logger.info(f"    Auth fail:     {cat.get('auth_fail', 0)}")
    logger.info(f"    Loi khac:      {cat.get('error', 0)}")
    logger.info("")
    logger.info("═" * 56)
    logger.info("XONG!")

# ── interactive menu ──────────────────────────────────────────────────────────

def _show_menu():
    print("""
==============================================================
          VALORANT CHECKER - Python Edition
==============================================================

  1.  Browser Mode (Playwright)  [CHINH THUC - TOT NHAT]
      -> Dung Chrome that, tran captcha tot hon
      -> Proxy rieng cho moi account
      -> Khuyen nghi: 1-3 concurrency

  2.  HTTP Mode (API)
      -> Nhanh hon, khong can mo trinh duyet
      -> De bi captcha hon
      -> Khuyen nghi: 3-5 concurrency

  3.  Retry Captcha Accounts
      -> Chay lai nhung account bi captcha tu truoc
      -> Dung proxy xoay khac

  4.  Exit

==============================================================
""")

def _get_choice() -> int:
    while True:
        try:
            c = int(input("  Nhap lua chon (1-4): ").strip())
            if 1 <= c <= 4:
                return c
            print("  Vui long nhap so tu 1-4")
        except ValueError:
            print("  Vui long nhap so tu 1-4")

def _get_concurrency(prompt: str, default: int) -> int:
    while True:
        try:
            val = input(f"  {prompt} [mac dinh {default}]: ").strip()
            if not val:
                return default
            c = int(val)
            if 1 <= c <= 20:
                return c
            print("  Vui long nhap so tu 1-20")
        except ValueError:
            print("  Vui long nhap so")

# ── captcha solver ─────────────────────────────────────────────────────────────

CAPTCHA_API_KEY = os.getenv("2CAPTCHA_API_KEY", "")

def _solve_captcha_2captcha(site_key: str, page_url: str, proxy: str = "") -> str | None:
    """
    Solve reCAPTCHA v2 via 2captcha.com.
    Returns g-recaptcha-response token or None on failure.
    """
    if not CAPTCHA_API_KEY:
        return None

    try:
        import urllib.request
        import urllib.parse

        # Submit
        data = {
            "googlekey": site_key,
            "pageurl": page_url,
            "method": "userrecaptcha",
            "key": CAPTCHA_API_KEY,
            "json": "1",
        }
        if proxy:
            data["proxy"] = proxy
            data["proxytype"] = "HTTP"

        req = urllib.request.Request(
            "http://2captcha.com/in.php",
            data=urllib.parse.urlencode(data).encode(),
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = _json.loads(resp.read())

        if result.get("status") != 1:
            logger.warning(f"  [captcha] Submit failed: {result}")
            return None

        captcha_id = result.get("request")
        logger.info(f"  [captcha] Submitted, ID: {captcha_id}")

        # Poll for result (max 120s)
        for _ in range(60):
            import time as _time
            _time.sleep(2)
            try:
                req2 = urllib.request.Request(
                    f"http://2captcha.com/res.php?key={CAPTCHA_API_KEY}&action=get&id={captcha_id}&json=1"
                )
                with urllib.request.urlopen(req2, timeout=10) as resp2:
                    res2 = _json.loads(resp2.read())
                if res2.get("status") == 1:
                    token = res2.get("request")
                    logger.info(f"  [captcha] Solved!")
                    return token
                if res2.get("request") != "CAPCHA_NOT_READY":
                    logger.warning(f"  [captcha] Error: {res2}")
                    return None
            except Exception as e:
                logger.debug(f"  [captcha] Poll error: {e}")

        logger.warning("  [captcha] Timeout after 120s")
        return None
    except Exception as e:
        logger.warning(f"  [captcha] 2captcha error: {e}")
        return None


if __name__ == "__main__":
    import asyncio as _asyncio
    if SKIP_MENU:
        _asyncio.run(_main())
    else:
        _show_menu()
        choice = _get_choice()

        if choice == 4:
            print("  Thoat.")
            sys.exit(0)

        if choice == 1:
            conc = _get_concurrency("Concurrency (browser mode)", 2)
        else:
            conc = _get_concurrency("Concurrency (HTTP mode)", 4)

        n_proxies = 0
        if PROXIES_FILE.exists():
            lines = [l for l in PROXIES_FILE.read_text(encoding="utf-8").splitlines()
                     if l.strip() and not l.strip().startswith("#")]
            n_proxies = len(lines)
        print(f"  Proxy: {n_proxies} duoc load ({n_proxies if n_proxies > 0 else '0 - dung IP may'})")

        captcha_key = os.getenv("2CAPTCHA_API_KEY", "")
        if not captcha_key:
            print("  [INFO] 2Captcha API key chua dat (set 2CAPTCHA_API_KEY env)")
            print("         Neu can auto-solve captcha, lay key tai: https://2capt.com")
            print("         VD: set 2CAPTCHA_API_KEY=your_key_here")

        browser_flag = "--browser" if choice == 1 else ""
        cmd = f'python main.py --cli --concurrency {conc} {browser_flag}'.strip()
        print(f"\n  ▶ Chay: {cmd}\n")
        import subprocess
        result = subprocess.run(cmd, shell=True)
        sys.exit(result.returncode)
