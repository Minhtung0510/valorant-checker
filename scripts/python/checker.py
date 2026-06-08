"""
checker.py — Valorant account checker with persistent refresh_token auth.

Token strategy (in order):
  1. Lockfile    — Valorant running on this machine → instant, no login
  2. Refresh token — saved in accounts.json → headless HTTP refresh (vĩnh viễn)
  3. Full login   — Playwright login + save refresh_token for next runs

Flow:
  First time  : Playwright login → save refresh_token → done
  Subsequent   : Headless HTTP refresh → new access_token → check
  After refresh fails: Full Playwright login again

If the account password is changed → refresh fails → re-login needed
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("checker")
if not logger.handlers:
    logger.addHandler(logging.StreamHandler(sys.stdout))
    logger.setLevel(logging.INFO)

# ── Paths ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
ACCOUNTS_FILE = SCRIPT_DIR / "accounts.json"


# ── Account DB ────────────────────────────────────────────────────────────────

@dataclass
class AccountConfig:
    username: str
    password: str
    region: str = "ap"


@dataclass
class AccountTokens:
    access_token: str
    entitlements_token: str
    puuid: str
    region: str
    expires_at: float  # unix timestamp when access_token expires
    refresh_token: str


def _load_accounts() -> dict[str, dict]:
    """Returns {username_lower: {username, password, region, tokens}}"""
    if not ACCOUNTS_FILE.exists():
        return {}
    try:
        return json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_accounts(data: dict):
    ACCOUNTS_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _get_account_tokens(username: str) -> Optional[AccountTokens]:
    data = _load_accounts()
    entry = data.get(username.lower())
    if not entry or not entry.get("tokens"):
        return None
    t = entry["tokens"]
    return AccountTokens(
        access_token=t["access_token"],
        entitlements_token=t["entitlements_token"],
        puuid=t["puuid"],
        region=t["region"],
        expires_at=t["expires_at"],
        refresh_token=t["refresh_token"],
    )


def _save_account_tokens(username: str, password: str, region: str, tokens: dict):
    """Save tokens for an account into accounts.json."""
    data = _load_accounts()
    key = username.lower()
    data[key] = {
        "username": username,
        "password": password,
        "region": region,
        "tokens": {
            "access_token":        tokens["access_token"],
            "entitlements_token": tokens["entitlements_token"],
            "puuid":              tokens["puuid"],
            "region":             tokens["region"],
            "expires_at":         tokens["expires_at"],
            "refresh_token":      tokens["refresh_token"],
        },
    }
    _save_accounts(data)
    logger.info(f"  [checker] Saved tokens for {username} → accounts.json")


def _remove_account_tokens(username: str):
    """Remove tokens when refresh fails (password changed)."""
    data = _load_accounts()
    key = username.lower()
    if key in data and "tokens" in data[key]:
        del data[key]["tokens"]
        _save_accounts(data)


# ── Token Manager ─────────────────────────────────────────────────────────────

class TokenManager:
    """Manages auth for one account at a time."""

    def __init__(self):
        self._client_version: Optional[str] = None

    # ── 1. Lockfile ──────────────────────────────────────────────────────

    def _lockfile_tokens(self) -> Optional[dict]:
        lockfile_path = Path(os.getenv(
            "LOCALAPPDATA",
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

        import base64, subprocess
        auth = base64.b64encode(f"riot:{password}".encode()).decode()
        url  = f"https://127.0.0.1:{port}/entitlements/v1/token"

        try:
            result = subprocess.run(
                ["curl", "-s", "-k", "-X", "GET", "-H", f"Authorization: Basic {auth}", url],
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
                "access_token":        at,
                "entitlements_token":  et,
                "puuid":               puuid,
                "region":              self._region_from_lockfile(port, password) or "ap",
                "expires_at":          datetime.now().timestamp() + 3600,
                "refresh_token":       "",
            }
        except Exception:
            return None

    def _region_from_lockfile(self, port: int, password: str) -> Optional[str]:
        import base64, subprocess, re
        auth = base64.b64encode(f"riot:{password}".encode()).decode()
        try:
            result = subprocess.run(
                ["curl", "-s", "-k", "-X", "GET",
                 "-H", f"Authorization: Basic {auth}",
                 f"https://127.0.0.1:{port}/product-session/v1/external-sessions"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                for session in json.loads(result.stdout).values():
                    for arg in session.get("launchConfiguration", {}).get("arguments", []):
                        import re as _re
                        m = _re.search(r"-ares-deployment=([a-z]+)", arg)
                        if m:
                            return m.group(1)
        except Exception:
            pass
        return None

    # ── 2. Client version ────────────────────────────────────────────────

    async def _get_client_version(self) -> str:
        if self._client_version:
            return self._client_version

        cache_file = SCRIPT_DIR / "riot_version.json"
        try:
            if cache_file.exists():
                cached = json.loads(cache_file.read_text())
                age = (datetime.now() - datetime.fromisoformat(cached["cached_at"])).total_seconds()
                if age < 3600:
                    self._client_version = cached["version"]
                    return self._client_version
        except Exception:
            pass

        import httpx
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get("https://valorant-api.com/v1/version")
                if resp.is_success:
                    version = resp.json()["data"]["riotClientVersion"]
                    self._client_version = version
                    cache_file.write_text(json.dumps({
                        "version": version,
                        "cached_at": datetime.now().isoformat(),
                    }))
                    return version
        except Exception:
            pass

        self._client_version = "release-12.10-shipping-17-4738152"
        return self._client_version

    # ── 3. Refresh token ────────────────────────────────────────────────

    async def _refresh_tokens(self, refresh_token: str) -> Optional[dict]:
        """Headless HTTP refresh — no browser needed."""
        try:
            from auth import refresh_access_token
        except ImportError:
            return None

        result = await refresh_access_token(refresh_token)
        if not result:
            return None

        access_token  = result.get("access_token", "")
        new_rt        = result.get("refresh_token", "") or refresh_token
        expires_in    = result.get("expires_in", 3600)

        if not access_token:
            return None

        # Get entitlements + puuid with the new token
        import httpx
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                ent_resp = await client.post(
                    "https://entitlements.auth.riotgames.com/api/token/v1",
                    headers=headers, json={},
                )
                entitlements = ent_resp.json().get("entitlements_token", "") if ent_resp.is_success else ""

                user_resp = await client.get(
                    "https://auth.riotgames.com/userinfo",
                    headers=headers,
                )
                user_data = user_resp.json() if user_resp.is_success else {}

            logger.info("  [checker] Token refreshed headlessly ✓")
            return {
                "access_token":        access_token,
                "entitlements_token":  entitlements,
                "puuid":               user_data.get("sub", ""),
                "region":              "ap",
                "expires_at":          datetime.now().timestamp() + expires_in,
                "refresh_token":       new_rt,
            }
        except Exception as e:
            logger.warning(f"  [checker] Could not get entitlements after refresh: {e}")
            return None

    # ── 4. Full login ──────────────────────────────────────────────────

    async def _full_login(self, username: str, password: str, region: str) -> Optional[dict]:
        """Riot Auth API login — fully headless, no browser."""
        from auth import login_with_password

        result = await login_with_password(username, password, region)
        if result.get("status") != "success":
            logger.warning(f"  [checker] Login failed: {result.get('status')}")
            return None

        access_token  = result.get("access_token", "")
        refresh_token = result.get("refresh_token", "")
        expires_in    = result.get("expires_in", 3600)

        if not access_token or not refresh_token:
            return None

        # Get entitlements
        import httpx
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                ent_resp = await client.post(
                    "https://entitlements.auth.riotgames.com/api/token/v1",
                    headers=headers, json={},
                )
                entitlements = ent_resp.json().get("entitlements_token", "") if ent_resp.is_success else ""

                user_resp = await client.get(
                    "https://auth.riotgames.com/userinfo",
                    headers=headers,
                )
                user_data = user_resp.json() if user_resp.is_success else {}

            logger.info("  [checker] Full login successful ✓")
            return {
                "access_token":        access_token,
                "entitlements_token":  entitlements,
                "puuid":               user_data.get("sub", ""),
                "region":              region,
                "expires_at":          datetime.now().timestamp() + expires_in,
                "refresh_token":       refresh_token,
            }
        except Exception as e:
            logger.warning(f"  [checker] Could not get entitlements after login: {e}")
            return None

    # ── Public: get tokens for one account ─────────────────────────────

    async def get_tokens(
        self,
        username: str,
        password: str,
        region: str = "ap",
    ) -> Optional[dict]:
        """
        Get valid tokens for an account.

        Strategy:
          1. Lockfile  → instant, no login
          2. Saved tokens in accounts.json → headless refresh
          3. Full Playwright login → save refresh_token for next runs
        """
        # Strategy 1: Lockfile
        tokens = self._lockfile_tokens()
        if tokens:
            logger.info("  [checker] Auth: lockfile ✓")
            return tokens

        # Strategy 2: Try refresh token from accounts.json
        saved_tokens = _get_account_tokens(username)
        if saved_tokens:
            # Check if token is still valid (with 5-min buffer)
            buffer = 300
            if saved_tokens.expires_at > datetime.now().timestamp() + buffer:
                # Token still fresh
                import httpx
                headers = {"Authorization": f"Bearer {saved_tokens.access_token}"}
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        ent_resp = await client.post(
                            "https://entitlements.auth.riotgames.com/api/token/v1",
                            headers=headers, json={},
                        )
                        entitlements = ent_resp.json().get("entitlements_token", "") if ent_resp.is_success else ""
                        user_resp = await client.get(
                            "https://auth.riotgames.com/userinfo",
                            headers=headers,
                        )
                        user_data = user_resp.json() if user_resp.is_success else {}
                    logger.info("  [checker] Auth: saved token still valid ✓")
                    return {
                        "access_token":        saved_tokens.access_token,
                        "entitlements_token":  entitlements or saved_tokens.entitlements_token,
                        "puuid":               user_data.get("sub", "") or saved_tokens.puuid,
                        "region":              saved_tokens.region,
                        "expires_at":          saved_tokens.expires_at,
                        "refresh_token":       saved_tokens.refresh_token,
                    }
                except Exception:
                    pass

            # Token expired or invalid → try refresh
            logger.info("  [checker] Auth: token expired — trying refresh_token...")
            if saved_tokens.refresh_token:
                refreshed = await self._refresh_tokens(saved_tokens.refresh_token)
                if refreshed:
                    _save_account_tokens(username, password, region, refreshed)
                    return refreshed
                else:
                    # Refresh failed = password changed
                    logger.warning(f"  [checker] Refresh failed — password may have changed")
                    _remove_account_tokens(username)

        # Strategy 3: Full login
        if username and password:
            logger.info(f"  [checker] Auth: full login for {username}...")
            tokens = await self._full_login(username, password, region)
            if tokens:
                _save_account_tokens(username, password, region, tokens)
                return tokens

        logger.warning("  [checker] Auth: all methods failed")
        return None


# ── Global manager ──────────────────────────────────────────────────────────────

_token_manager: Optional[TokenManager] = None

def get_token_manager() -> TokenManager:
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
    return _token_manager


# ── Rank names & constants ──────────────────────────────────────────────────────

_RANK_NAMES = [
    "Unrated", "Iron 1", "Iron 2", "Iron 3",
    "Bronze 1", "Bronze 2", "Bronze 3",
    "Silver 1", "Silver 2", "Silver 3",
    "Gold 1", "Gold 2", "Gold 3",
    "Platinum 1", "Platinum 2", "Platinum 3",
    "Diamond 1", "Diamond 2", "Diamond 3",
    "Ascendant 1", "Ascendant 2", "Ascendant 3",
    "Immortal 1", "Immortal 2", "Immortal 3",
    "Radiant",
]

_RIOT_PLATFORM = (
    "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVm"
    "Vyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9"
)

_UUID_SKINS = "e7c63390-eda7-46e0-bb7a-a6abdacd2433"


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class AccountResult:
    ok: bool
    status: str
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
    vp: int
    rp: int
    kc: int
    fa: int
    skins_count: int
    ban_reason: str
    email_verified: bool
    phone_verified: bool
    country: str
    created_at: str
    error: str = ""


# ── API calls ────────────────────────────────────────────────────────────────

async def _riot_request(
    method: str, url: str,
    access_token: str, entitlements_token: str, client_version: str,
    **kwargs,
) -> Optional[dict]:
    import httpx
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Riot-Entitlements-JWT": entitlements_token,
        "X-Riot-ClientVersion": client_version,
        "X-Riot-ClientPlatform": _RIOT_PLATFORM,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.request(method, url, headers=headers, **kwargs)
            if resp.status_code in (403, 404):
                return {"_error": resp.status_code}
            if resp.is_success:
                return resp.json()
            return None
    except Exception:
        return None


async def _fetch_userinfo(access_token: str, entitlements_token: str, client_version: str) -> dict:
    return await _riot_request(
        "GET", "https://auth.riotgames.com/userinfo",
        access_token, entitlements_token, client_version,
    ) or {}


async def _fetch_wallet(access_token: str, entitlements_token: str, cv: str, puuid: str, region: str) -> dict:
    result = await _riot_request(
        "GET", f"https://pd.{region.lower()}.a.pvp.net/store/v1/wallet/{puuid}",
        access_token, entitlements_token, cv,
    )
    if not result:
        return {"vp": 0, "rp": 0, "kc": 0, "fa": 0}
    bals = result.get("Balances", {})
    uuids = list(bals.keys())
    return {
        "vp": int(bals.get(uuids[0], 0)) if len(uuids) > 0 else 0,
        "rp": int(bals.get(uuids[1], 0)) if len(uuids) > 1 else 0,
        "kc": int(bals.get(uuids[2], 0)) if len(uuids) > 2 else 0,
        "fa": int(bals.get(uuids[3], 0)) if len(uuids) > 3 else 0,
    }


async def _fetch_mmr(access_token: str, entitlements_token: str, cv: str, puuid: str, region: str) -> tuple[int, int]:
    result = await _riot_request(
        "GET", f"https://pd.{region.lower()}.a.pvp.net/mmr/v1/players/{puuid}",
        access_token, entitlements_token, cv,
    )
    if not result or result.get("_error"):
        return 0, 0
    
    # Use LatestCompetitiveUpdate like web app (current rank from latest match)
    comp = result.get("LatestCompetitiveUpdate", {})
    tier = int(comp.get("TierAfterUpdate", 0))
    rr = int(comp.get("RankedRatingAfterUpdate", 0))
    if tier > 0:
        return tier, rr
    
    # Fallback: seasonal info
    seasons = result.get("QueueSkills", {}).get("competitive", {}).get("SeasonalInfoBySeasonID", {})
    if not seasons:
        return 0, 0
    latest = max(seasons.keys())
    info = seasons[latest]
    return int(info.get("CompetitiveTier", 0)), int(info.get("RankedRating", 0))


async def _fetch_account_xp(access_token: str, entitlements_token: str, cv: str, puuid: str, region: str) -> int:
    result = await _riot_request(
        "GET", f"https://pd.{region.lower()}.a.pvp.net/account-xp/v1/players/{puuid}",
        access_token, entitlements_token, cv,
    )
    if not result:
        return 0
    return int(result.get("Progress", {}).get("Level", result.get("Level", 0)))


async def _fetch_skins(access_token: str, entitlements_token: str, cv: str, puuid: str, region: str) -> int:
    result = await _riot_request(
        "GET", f"https://pd.{region.lower()}.a.pvp.net/store/v1/entitlements/{puuid}/{_UUID_SKINS}",
        access_token, entitlements_token, cv,
    )
    if not result:
        return 0
    return len(result.get("Entitlements", []))


async def _fetch_ranked_restrictions(access_token: str, entitlements_token: str, cv: str, puuid: str, region: str) -> list:
    result = await _riot_request(
        "GET", f"https://pd.{region.lower()}.a.pvp.net/restrictions/v1/players/{puuid}/restrictions",
        access_token, entitlements_token, cv,
    )
    return (result or {}).get("restrictions", [])


# ── Main function ─────────────────────────────────────────────────────────────

async def check_account(
    username: str,
    password: str,
    region: str = "ap",
) -> AccountResult:
    """
    Check a single Valorant account.

    Auth strategy:
      1. Lockfile → instant token, no login
      2. Refresh token → headless HTTP, no browser
      3. Full Playwright login → save refresh_token for next runs

    Returns AccountResult. Use .ok to know if account is safe to sell.

    Example:
        result = await check_account("my@email.com", "mypass", "ap")
        if result.ok:
            print(f"✅ {result.game_name}#{result.tag_line} — {result.rank_str}")
        else:
            print(f"❌ {result.status_label}: {result.ban_reason}")
    """
    tm = get_token_manager()
    client_version = await tm._get_client_version()

    # ── Auth ──────────────────────────────────────────────────────────────
    tokens = await tm.get_tokens(username=username, password=password, region=region)
    if not tokens:
        return AccountResult(
            ok=False, status="error", status_label="AUTH FAILED",
            username=username, game_name="", tag_line="",
            puuid="", region=region,
            level=0, rank_str="", current_tier=0, current_rr=0,
            vp=0, rp=0, kc=0, fa=0, skins_count=0,
            ban_reason="", email_verified=False, phone_verified=False,
            country="", created_at="",
            error="auth_failed",
        )

    access_token        = tokens["access_token"]
    entitlements_token = tokens["entitlements_token"]
    puuid               = tokens.get("puuid", "")
    region              = tokens.get("region", region) or region

    # ── User info ────────────────────────────────────────────────────────
    userinfo = await _fetch_userinfo(access_token, entitlements_token, client_version)
    if not userinfo:
        return AccountResult(
            ok=False, status="error", status_label="TOKEN INVALID",
            username=username, game_name="", tag_line="",
            puuid=puuid, region=region,
            level=0, rank_str="", current_tier=0, current_rr=0,
            vp=0, rp=0, kc=0, fa=0, skins_count=0,
            ban_reason="", email_verified=False, phone_verified=False,
            country="", created_at="",
            error="token_invalid",
        )

    game_name = userinfo.get("game_name", username.split("@")[0])
    tag_line  = userinfo.get("tag_line", "")
    if not puuid:
        puuid = userinfo.get("sub", "")

    # ── Parallel data fetch ─────────────────────────────────────────────
    wallet_task       = _fetch_wallet(access_token, entitlements_token, client_version, puuid, region)
    mmr_task          = _fetch_mmr(access_token, entitlements_token, client_version, puuid, region)
    skins_task        = _fetch_skins(access_token, entitlements_token, client_version, puuid, region)
    xp_task           = _fetch_account_xp(access_token, entitlements_token, client_version, puuid, region)
    restrictions_task = _fetch_ranked_restrictions(access_token, entitlements_token, client_version, puuid, region)

    wallet_data, (tier, rr), skins_count, level, restrictions = await asyncio.gather(
        wallet_task, mmr_task, skins_task, xp_task, restrictions_task,
    )

    # ── Determine status ─────────────────────────────────────────────────
    ban_reason   = ""
    status       = "active"
    status_label = "✅ ACTIVE"

    if restrictions:
        r      = restrictions[0]
        rtype  = r.get("type", "")
        reason = r.get("reason", "")
        if "PERMANENT" in rtype.upper():
            status       = "perm_ban"
            status_label = "🚫 BI CAM VINH VIEN"
            ban_reason   = reason or rtype
        else:
            rest_until = r.get("rest_until")
            if rest_until:
                status_label = f"⏸ BI KHOA den {datetime.fromtimestamp(rest_until / 1000, tz=timezone.utc).strftime('%d/%m/%Y')}"
            else:
                status_label = "⏸ BI KHOA TAM THOI"
            status     = "suspended"
            ban_reason = reason or rtype

    if not restrictions:
        ban_data = userinfo.get("ban") or {}
        if ban_data.get("flag"):
            ban_reason   = ban_data["flag"]
            status       = "perm_ban"
            status_label = "🚫 BI CAM"
        elif ban_data.get("restrictions"):
            bans = ban_data["restrictions"]
            if bans:
                r = bans[0]
                if "PERMANENT" in r.get("type", "").upper():
                    status       = "perm_ban"
                    status_label = "🚫 BI CAM VINH VIEN"
                    ban_reason   = r.get("reason", "")
                else:
                    status       = "suspended"
                    status_label = "⏸ BI KHOA"
                    ban_reason   = r.get("reason", "")

    ok = status == "active"
    rank_label = _RANK_NAMES[tier] if 0 <= tier < len(_RANK_NAMES) else f"Rank {tier}"
    rank_str   = f"{rank_label} — {rr} RR" if tier > 0 else "Unrated"

    created_at = ""
    if userinfo.get("acct", {}).get("created_at"):
        try:
            created_at = datetime.fromisoformat(
                userinfo["acct"]["created_at"].replace("Z", "+00:00")
            ).strftime("%d/%m/%Y")
        except Exception:
            created_at = userinfo["acct"]["created_at"]

    return AccountResult(
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
        vp=wallet_data.get("vp", 0),
        rp=wallet_data.get("rp", 0),
        kc=wallet_data.get("kc", 0),
        fa=wallet_data.get("fa", 0),
        skins_count=skins_count,
        ban_reason=ban_reason,
        email_verified=userinfo.get("email_verified", False),
        phone_verified=userinfo.get("phone_number_verified", False),
        country=userinfo.get("country", ""),
        created_at=created_at,
    )
