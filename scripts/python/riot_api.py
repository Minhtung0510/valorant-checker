"""
riot_api.py — All Riot API calls (async httpx)
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from config import (
    RIOT_PLATFORM,
    UUID_SKINS,
    HTTPX_TIMEOUT, HTTPX_MAX_RETRIES,
    RANK_NAMES,
)

logger = logging.getLogger("riot_api")

# ── helpers ──────────────────────────────────────────────────────────────────

async def _retry_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs,
) -> httpx.Response:
    """Send request with exponential backoff retry (1s, 2s, 4s)."""
    last_err = None
    for attempt in range(HTTPX_MAX_RETRIES):
        try:
            resp = await client.request(method, url, **kwargs)
            if resp.status_code == 429:
                logger.warning(f"  429 rate-limit — sleeping 60s then retrying...")
                await asyncio.sleep(60)
                continue
            return resp
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_err = e
            if attempt < HTTPX_MAX_RETRIES - 1:
                await asyncio.sleep(2 ** attempt)
    raise last_err or RuntimeError("All retries failed")


def _riot_headers(access_token: str, entitlements_token: str, client_version: str):
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Riot-Entitlements-JWT": entitlements_token,
        "X-Riot-ClientVersion": client_version,
        "X-Riot-ClientPlatform": RIOT_PLATFORM,
    }


# ── version ──────────────────────────────────────────────────────────────────

async def get_client_version() -> str:
    """Fetch once per run, cache in calling code."""
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get("https://valorant-api.com/v1/version")
            resp.raise_for_status()
            return resp.json()["data"]["riotClientVersion"]
        except Exception as e:
            logger.warning(f"  Could not fetch client version: {e}")
            return "release-12.10-shipping-17-4738152"


# ── auth ────────────────────────────────────────────────────────────────────

async def fetch_entitlement(access_token: str) -> str:
    """POST /api/token/v1 → entitlements_token"""
    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        resp = await client.post(
            "https://entitlements.auth.riotgames.com/api/token/v1",
            headers={"Authorization": f"Bearer {access_token}"},
            json={},
        )
        if not resp.is_success:
            return ""
        return resp.json().get("entitlements_token", "")


async def fetch_userinfo(access_token: str) -> dict:
    """GET /userinfo → full user data including ban info"""
    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        resp = await client.get(
            "https://auth.riotgames.com/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if not resp.is_success:
            return {}
        return resp.json()


# ── pd endpoints ────────────────────────────────────────────────────────────

async def fetch_wallet(
    access_token: str,
    entitlements_token: str,
    client_version: str,
    puuid: str,
    region: str,
) -> dict:
    """GET /store/v1/wallet/{puuid} → {vp, rp, kc, fa}"""
    from config import UUID_SKINS
    host = f"pd.{region.lower()}.a.pvp.net"
    headers = _riot_headers(access_token, entitlements_token, client_version)
    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        resp = await _retry_request(client, "GET", f"https://{host}/store/v1/wallet/{puuid}", headers=headers)
        if not resp.is_success:
            return {"vp": 0, "rp": 0, "kc": 0, "fa": 0}
        balances: dict = resp.json().get("Balances", {})
        uuid_list = list(balances.keys())
        return {
            "vp": int(balances.get(uuid_list[0], 0)) if len(uuid_list) > 0 else 0,
            "rp": int(balances.get(uuid_list[1], 0)) if len(uuid_list) > 1 else 0,
            "kc": int(balances.get(uuid_list[2], 0)) if len(uuid_list) > 2 else 0,
            "fa": int(balances.get(uuid_list[3], 0)) if len(uuid_list) > 3 else 0,
        }


async def fetch_account_xp(
    access_token: str,
    entitlements_token: str,
    client_version: str,
    puuid: str,
    region: str,
) -> dict:
    """GET /account-xp/v1/players/{puuid} → {level}"""
    host = f"pd.{region.lower()}.a.pvp.net"
    headers = _riot_headers(access_token, entitlements_token, client_version)
    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        resp = await _retry_request(client, "GET", f"https://{host}/account-xp/v1/players/{puuid}", headers=headers)
        if not resp.is_success:
            return {"level": 0}
        data = resp.json()
        return {"level": data.get("Progress", {}).get("Level", data.get("Level", 0))}


async def fetch_mmr(
    access_token: str,
    entitlements_token: str,
    client_version: str,
    puuid: str,
    region: str,
) -> tuple[int, int]:
    """GET /mmr/v1/players/{puuid} → (tier, rr)"""
    host = f"pd.{region.lower()}.a.pvp.net"
    headers = _riot_headers(access_token, entitlements_token, client_version)
    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        resp = await _retry_request(client, "GET", f"https://{host}/mmr/v1/players/{puuid}", headers=headers)
        if not resp.is_success:
            return 0, 0
        data = resp.json()
        
        # Use LatestCompetitiveUpdate like web app (current rank from latest match)
        comp = data.get("LatestCompetitiveUpdate", {})
        tier = int(comp.get("TierAfterUpdate", 0))
        rr = int(comp.get("RankedRatingAfterUpdate", 0))
        if tier > 0:
            return tier, rr
        
        # Fallback: seasonal info
        queue = data.get("QueueSkills", {}).get("competitive", {})
        info_list = queue.get("SeasonalInfoBySeasonID", {})
        if not info_list:
            return 0, 0
        latest_key = max(info_list.keys())
        info = info_list[latest_key]
        return int(info.get("CompetitiveTier", 0)), int(info.get("RankedRating", 0))


async def fetch_mmr_ban(
    access_token: str,
    entitlements_token: str,
    client_version: str,
    puuid: str,
    region: str,
) -> tuple[bool, str]:
    """
    GET /mmr/v1/players/{puuid} → detect game ban.
    Returns (is_banned, ban_reason).
    """
    host = f"pd.{region.lower()}.a.pvp.net"
    headers = _riot_headers(access_token, entitlements_token, client_version)
    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        resp = await _retry_request(client, "GET", f"https://{host}/mmr/v1/players/{puuid}", headers=headers)
        # 403/404 = account banned or region locked
        if resp.status_code in (403, 404):
            return True, "GAME_BAN_OR_LOCKED"
        if not resp.is_success:
            return False, ""
        return False, ""


async def fetch_ranked_restrictions(
    access_token: str,
    entitlements_token: str,
    client_version: str,
    puuid: str,
    region: str,
) -> dict:
    """
    GET /restrictions/v1/players/{puuid}/restrictions
    → returns { restrictions: [...], error_code, error_msg }
    No restriction = account can queue ranked freely.
    Common restriction types:
      - SMS_VERIFY      : chưa verify SMS cho ranked
      - EMAIL_VERIFY    : chưa verify email
      - LEAGUE_OF_LEGENDS_TERMS: chưa accept ToS
      - COMPETITIVE_TOKENS_EXHAUSTED: hết token (thường do full queue)
    """
    host = f"pd.{region.lower()}.a.pvp.net"
    headers = _riot_headers(access_token, entitlements_token, client_version)
    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        resp = await client.get(
            f"https://{host}/restrictions/v1/players/{puuid}/restrictions",
            headers=headers,
        )
        if resp.is_success:
            return {"restrictions": resp.json().get("restrictions", [])}
        if resp.status_code == 404:
            return {"restrictions": []}
        if resp.status_code in (400, 403):
            try:
                data = resp.json()
                return {
                    "restrictions": [],
                    "error_code": data.get("errorCode", ""),
                    "error_msg": data.get("message", ""),
                }
            except Exception:
                pass
        return {"restrictions": [], "error_code": str(resp.status_code)}


async def fetch_skins_count(
    access_token: str,
    entitlements_token: str,
    client_version: str,
    puuid: str,
    region: str,
) -> int:
    """GET /stores/v1/entitlements/{puuid}/<skin_uuid> → count"""
    host = f"pd.{region.lower()}.a.pvp.net"
    headers = _riot_headers(access_token, entitlements_token, client_version)
    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        resp = await _retry_request(
            client, "GET",
            f"https://{host}/stores/v1/entitlements/{puuid}/{UUID_SKINS}",
            headers=headers,
        )
        if not resp.is_success:
            return 0
        ents: list = resp.json().get("Entitlements", [])
        return len(ents)


# ── orchestrator ────────────────────────────────────────────────────────────

async def fetch_all(
    access_token: str,
    entitlements_token: str,
    client_version: str,
    puuid: str,
    region: str,
) -> dict:
    """
    Parallel fetch wallet, mmr, skins, ranked restrictions.
    Returns dict ready for sheets.update_row().
    """
    wallet_task = fetch_wallet(access_token, entitlements_token, client_version, puuid, region)
    mmr_task = fetch_mmr(access_token, entitlements_token, client_version, puuid, region)
    skins_task = fetch_skins_count(access_token, entitlements_token, client_version, puuid, region)
    restrictions_task = fetch_ranked_restrictions(access_token, entitlements_token, client_version, puuid, region)

    wallet_data, mmr_data, skins_count, restrictions_data = await asyncio.gather(
        wallet_task, mmr_task, skins_task, restrictions_task,
    )

    tier, rr = mmr_data
    rank_label = RANK_NAMES[tier] if 0 <= tier < len(RANK_NAMES) else f"Rank {tier}"
    rank_str = f"{rank_label} — {rr} RR" if tier > 0 else "Unrated"

    # Build ranked_restriction string
    ranked_restriction: str | None = None
    raw_restrictions = restrictions_data.get("restrictions", [])
    if raw_restrictions:
        types = [r.get("type", "") or r.get("reason", "") for r in raw_restrictions]
        ranked_restriction = "; ".join(filter(None, types))
    elif restrictions_data.get("error_code"):
        ranked_restriction = f"[{restrictions_data['error_code']}] {restrictions_data.get('error_msg', '')}"

    return {
        "vp": wallet_data["vp"],
        "rp": wallet_data["rp"],
        "kc": wallet_data["kc"],
        "skins_count": skins_count,
        "rank_str": rank_str,
        "current_tier": tier,
        "current_rr": rr,
        "ranked_restriction": ranked_restriction,
    }
