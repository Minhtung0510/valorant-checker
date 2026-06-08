"""
auth_lockfile.py — Lockfile-based auth: reads tokens directly from a running
Riot Client / Valorant instance (no login required).

Usage:
    from auth_lockfile import get_local_tokens
    tokens = get_local_tokens()
    # tokens = {"access_token": ..., "entitlements_token": ..., "puuid": ..., "region": ...}
"""
import base64
import json
import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("auth_lockfile")

# ── Lockfile path ─────────────────────────────────────────────────────────────

LOCKFILE_PATH = Path(os.getenv(
    "LOCALAPPDATA",
    os.path.expanduser("~\\AppData\\Local")
)) / "Riot Games" / "Riot Client" / "Config" / "lockfile"


def _read_lockfile() -> Optional[dict]:
    """Read and parse the Riot Client lockfile. Returns None if not found."""
    if not LOCKFILE_PATH.exists():
        logger.debug(f"Lockfile not found at {LOCKFILE_PATH}")
        return None
    try:
        content = LOCKFILE_PATH.read_text(encoding="utf-8").strip()
        parts = content.split(":")
        if len(parts) < 5:
            return None
        return {
            "name":     parts[0],
            "pid":      int(parts[1]),
            "port":     int(parts[2]),
            "password": parts[3],
            "protocol": parts[4],
        }
    except Exception as e:
        logger.debug(f"Failed to read lockfile: {e}")
        return None


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def _basic_auth(username: str, password: str) -> str:
    credentials = f"{username}:{password}"
    return base64.b64encode(credentials.encode()).decode()


def _http_get(url: str, headers: dict, timeout: float = 5.0) -> Optional[dict]:
    try:
        result = subprocess.run(
            ["curl", "-s", "-X", "GET", "-k",
             "-H", f"Authorization: Basic {headers['Authorization'].replace('Basic ', '')}",
             "-H", f"X-Riot-Entitlements-JWT: {headers.get('X-Riot-Entitlements-JWT', '')}",
             url],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
        return None
    except Exception as e:
        logger.debug(f"HTTP GET failed: {e}")
        return None


def _http_post(url: str, headers: dict, json_body: dict = None, timeout: float = 5.0) -> Optional[dict]:
    try:
        cmd = ["curl", "-s", "-X", "POST", "-k",
               "-H", f"Authorization: Basic {headers['Authorization'].replace('Basic ', '')}",
               "-H", "Content-Type: application/json"]
        if json_body:
            import tempfile
            body_file = os.path.join(tempfile.gettempdir(), "riot_post_body.json")
            Path(body_file).write_text(json.dumps(json_body), encoding="utf-8")
            cmd += ["-d", f"@{body_file}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout)
        return None
    except Exception as e:
        logger.debug(f"HTTP POST failed: {e}")
        return None


# ── Local token fetching ──────────────────────────────────────────────────────

def get_local_tokens() -> Optional[dict]:
    """
    Read access_token, entitlements_token, puuid, and region from a running
    Riot Client / Valorant instance via the local lockfile API.

    Returns None if Riot Client is not running.

    The token returned has a ~1 hour TTL — call this at the start of each bot run.
    """
    lockfile = _read_lockfile()
    if not lockfile:
        return None

    port     = lockfile["port"]
    password = lockfile["password"]
    auth     = _basic_auth("riot", password)
    headers  = {"Authorization": f"Basic {auth}"}

    # 1. Get entitlements + access token + puuid from the entitlements endpoint
    entitlements_url = f"https://127.0.0.1:{port}/entitlements/v1/token"
    ent_data = _http_get(entitlements_url, headers)
    if not ent_data:
        logger.debug("Could not fetch entitlements from local API")
        return None

    access_token        = ent_data.get("accessToken", "")
    entitlements_token = ent_data.get("token", "")
    puuid              = ent_data.get("subject", "")

    if not access_token or not entitlements_token:
        logger.debug("Entitlements response missing token fields")
        return None

    # 2. Get region from the client config
    region = _get_region_from_local_api(port, auth)
    if not region:
        region = _get_region_from_logs()
        if region:
            logger.info(f"  Region from ShooterGame log: {region}")
        else:
            region = "ap"

    logger.info(f"  [Lockfile] PUUID: {puuid[:8]}... | Region: {region}")
    return {
        "access_token":        access_token,
        "entitlements_token": entitlements_token,
        "puuid":              puuid,
        "region":             region,
    }


def _get_region_from_local_api(port: int, auth: str) -> Optional[str]:
    """Try to get region from the local Riot Client sessions API."""
    headers = {"Authorization": f"Basic {auth}"}
    url = f"https://127.0.0.1:{port}/product-session/v1/external-sessions"
    data = _http_get(url, headers)
    if not data:
        return None
    for session in data.values():
        args = session.get("launchConfiguration", {}).get("arguments", [])
        for arg in args:
            m = re.search(r"-ares-deployment=([a-z]+)", arg)
            if m:
                return m.group(1)
    return None


def _get_region_from_logs() -> Optional[str]:
    """
    Scrape the most recent ShooterGame.log for a region identifier.
    Path pattern: %LOCALAPPDATA%/Riot Games/VALORANT/Saved/Logs/...
    """
    log_dir = Path(os.getenv(
        "LOCALAPPDATA",
        os.path.expanduser("~\\AppData\\Local")
    )) / "Riot Games" / "VALORANT" / "Saved" / "Logs"
    if not log_dir.exists():
        return None

    # Find the most recent log file
    try:
        log_files = sorted(log_dir.glob("ShooterGame*.log"), key=lambda f: f.stat().st_mtime)
        if not log_files:
            return None
        # Check last 2 files, last 100KB each
        for lf in reversed(log_files[-2:]):
            try:
                content = lf.read_text(encoding="utf-8", errors="ignore")[-100_000:]
                for match in re.finditer(r'(?:ares-deployment|pd\.([a-z]+)\.a\.pvp\.net)', content):
                    if match.group(1):
                        return match.group(1)
            except Exception:
                continue
    except Exception:
        pass
    return None


# ── Cookie-based session (Playwright) ────────────────────────────────────────

COOKIE_SESSION_FILE = Path(__file__).parent / "riot_session.json"


def save_riot_cookies(cookies: list):
    """Save browser cookies to a local file for reuse."""
    COOKIE_SESSION_FILE.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
    logger.info(f"  Saved {len(cookies)} cookies to {COOKIE_SESSION_FILE}")


def load_riot_cookies() -> Optional[list]:
    """Load saved browser cookies. Returns None if no session file exists."""
    if not COOKIE_SESSION_FILE.exists():
        return None
    try:
        cookies = json.loads(COOKIE_SESSION_FILE.read_text(encoding="utf-8"))
        return cookies
    except Exception as e:
        logger.warning(f"Failed to load cookie session: {e}")
        return None


def clear_riot_cookies():
    """Delete the saved cookie session."""
    if COOKIE_SESSION_FILE.exists():
        COOKIE_SESSION_FILE.unlink()
        logger.info("  Cleared saved Riot session cookies")


# ── Entry point for bot ───────────────────────────────────────────────────────

def get_tokens() -> Optional[dict]:
    """
    Main entry point: tries lockfile first (Riot Client running),
    falls back to cookie session if available.
    Returns None if no valid session found.
    """
    # Try 1: Riot Client / Valorant is running
    tokens = get_local_tokens()
    if tokens:
        logger.info("  Using tokens from running Riot Client (lockfile)")
        return tokens

    # Try 2: Saved cookie session
    cookies = load_riot_cookies()
    if cookies:
        logger.info(f"  Found saved cookie session ({len(cookies)} cookies)")
        # Return a marker dict so the caller knows to re-login to refresh cookies
        return {"_has_cookies": cookies}

    logger.info("  No Riot Client running and no saved session — manual login required")
    return None
