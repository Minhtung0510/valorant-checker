"""
auth.py - Valorant account authentication.

Auth strategy (in order of priority):
  1. Lockfile tokens  — Valorant running → instant, no login needed
  2. Cookie session   — saved from previous headful login → re-auth silently
  3. Headful login   — Playwright opens real Chrome → user logs in once
                         → tokens + cookies saved for future runs

Headful mode (strategy 3) is NOT detected as automation because:
  - Uses real Chrome browser window
  - Real user profile
  - Same fingerprint as regular browsing

hCaptcha auto-solve via 2captcha.com:
  - Set env: set 2CAPTCHA_API_KEY=your_key
  - Supports retry up to CAPTCHA_MAX_RETRIES times
"""
from __future__ import annotations

import asyncio
from dotenv import load_dotenv
load_dotenv()

import json as _json
import logging
import os
import secrets
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

import httpx

logger = logging.getLogger("auth")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)

# ── Shared browser (Bug 1 fix) ─────────────────────────────────────────────────
# FIX: Previously each account spawned its own Node.js subprocess + Chromium instance.
# Multiple concurrent browsers exhaust memory and crash on Windows.
# Solution: launch ONE browser at startup, each account gets its own Context.

_pw_instance = None
_browser_instance = None
_browser_lock = asyncio.Lock()


async def _get_shared_browser(headless: bool):
    """
    Returns a shared Chromium instance. Lazily launches on first call.
    Each caller is responsible for creating their own BrowserContext.
    """
    global _pw_instance, _browser_instance
    async with _browser_lock:
        if _browser_instance is None:
            from playwright.async_api import async_playwright
            _pw_instance = await async_playwright().start()
            # NOTE: --no-sandbox and --disable-gpu are Linux/Docker flags.
            # On Windows they cause instant Chromium crashes. Removed.
            _browser_instance = await _pw_instance.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-extensions",
                ],
            )
            logger.info("  [browser] shared Chromium launched")
    return _browser_instance


async def _close_shared_browser():
    """Cleanup: called once at program exit."""
    global _pw_instance, _browser_instance
    if _browser_instance:
        await _browser_instance.close()
        _browser_instance = None
    if _pw_instance:
        await _pw_instance.stop()
        _pw_instance = None
        logger.info("  [browser] shared Chromium closed")

SCRIPT_DIR = Path(__file__).parent
SCREENSHOT_DIR = SCRIPT_DIR / "logs" / "screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# ── Paths ───────────────────────────────────────────────────────────────────────

COOKIE_SESSION_FILE = SCRIPT_DIR / "riot_session.json"
ACCOUNTS_FILE = SCRIPT_DIR / "accounts.json"


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _ss_name(label: str, username: str) -> str:
    import time
    ts = time.strftime("%H%M%S")
    safe = username.replace("@", "_at_").replace(".", "_")
    return str(SCREENSHOT_DIR / f"{safe}_{ts}_{label}.png")


async def _take_ss(page, label: str, username: str) -> str:
    import sys
    path = _ss_name(label, username)
    try:
        await page.screenshot(path=path, full_page=True)
        print(f"  [screenshot] {path}", flush=True, file=sys.stderr)
    except Exception as exc:
        print(f"  [screenshot] Failed: {exc}", flush=True, file=sys.stderr)
    return path


async def _fill_input(page, selector: str, value: str) -> bool:
    """Fill an input with retry and fallback."""
    try:
        el = await page.wait_for_selector(selector, timeout=30_000)
        await el.scroll_into_view_if_needed()
        await asyncio.sleep(0.3)
        try:
            await el.fill(value, timeout=3_000)
        except Exception:
            await el.click()
            await asyncio.sleep(0.15)
            await page.keyboard.press("Control+a")
            await asyncio.sleep(0.05)
            await page.keyboard.type(value, delay=20)
            await asyncio.sleep(0.2)
        await asyncio.sleep(0.3)
        actual = await page.evaluate(
            f"document.querySelector('{selector}')?.value || ''"
        )
        return bool(actual.strip())
    except Exception:
        return False


async def _click_sign_in(page) -> bool:
    """Click the Sign In button."""
    try:
        btn = await page.query_selector('[data-testid="btn-signin-submit"]')
        if btn:
            disabled = await btn.get_attribute("disabled")
            if disabled is None:
                await btn.click()
                return True
        for b in await page.query_selector_all("button"):
            try:
                svg = await b.query_selector('svg path[d*="22.8"]')
                if svg:
                    disabled = await b.get_attribute("disabled")
                    if disabled is None:
                        await b.click()
                        return True
            except Exception:
                pass
        for b in await page.query_selector_all("button"):
            try:
                text = (await b.inner_text()).strip().lower()
                if any(k in text for k in ["sign in", "log in", "login"]):
                    disabled = await b.get_attribute("disabled")
                    if disabled is None:
                        await b.click()
                        return True
            except Exception:
                pass
        await page.keyboard.press("Control+Enter")
        return True
    except Exception:
        return False


async def _is_blocked(page) -> bool:
    try:
        txt = (await page.inner_text("body")).lower()
        return any(k in txt for k in ["access denied", "blocked", "try again later", "too many requests"])
    except Exception:
        return False


async def _is_magic_link(page) -> bool:
    try:
        txt = (await page.inner_text("body")).lower()
        return any(k in txt for k in ["check your email", "sign in link", "verify your email"])
    except Exception:
        return False


# ── hCaptcha detection & auto-solve ───────────────────────────────────────────

# Provider detection: set one of these env vars
CAPTCHA_2CAPTCHA_KEY   = os.getenv("2CAPTCHA_API_KEY", "")
CAPTCHA_ANTICAPTCHA    = os.getenv("ANTI_CAPTCHA_API_KEY", "")
CAPTCHA_CAPMONSTER     = os.getenv("CAPMONSTER_API_KEY", "")
CAPTCHA_CAPSOLVER      = os.getenv("CAPSOLVER_API_KEY", "")

CAPTCHA_MAX_RETRIES  = int(os.getenv("CAPTCHA_MAX_RETRIES", "3"))
CAPTCHA_POLL_DELAY    = 5   # seconds between polls


def _get_provider() -> str:
    if CAPTCHA_CAPSOLVER:
        return "capsolver"
    if CAPTCHA_ANTICAPTCHA:
        return "anticaptcha"
    if CAPTCHA_CAPMONSTER:
        return "capmonster"
    if CAPTCHA_2CAPTCHA_KEY:
        return "2captcha"
    return ""


async def _is_hcaptcha_on_page(page) -> dict | None:
    """
    Detect hCaptcha iframe on the current page.
    Returns dict with keys 'site_key', 'url' if found, else None.
    """
    try:
        import re as _re
        body_html = await page.content()

        # 1. Check sitekey in parent page HTML
        patterns = [
            r'"sitekey"\s*:\s*"([^"]+)"',
            r'data-sitekey="([^"]+)"',
            r'sitekey=([a-zA-Z0-9\-]{20,})',
        ]
        for pat in patterns:
            m = _re.search(pat, body_html, _re.IGNORECASE)
            if m:
                site_key = m.group(1)
                if len(site_key) >= 20:
                    return {"site_key": site_key, "page_url": page.url}

        # 2. Check sitekey in ALL frame URLs (iframe src attributes)
        frames = page.frames
        for frame in frames:
            frame_url = frame.url
            m = _re.search(r'sitekey=([a-zA-Z0-9\-]{20,})', frame_url, _re.IGNORECASE)
            if m:
                return {"site_key": m.group(1), "page_url": frame_url}

        return None
    except Exception:
        return None


async def _solve_hcaptcha(site_key: str, page_url: str, proxy: str = "") -> str | None:
    """
    Solve hCaptcha via any configured provider.
    Providers (in priority order):
      1. CAPSOLVER_API_KEY   — https://capsolver.com  (~1.99$/1K)
      2. ANTI_CAPTCHA_API_KEY — https://anti-captcha.com (~2.00$/1K)
      3. CAPMONSTER_API_KEY   — https://capmonster.cloud (~2.00$/1K)
      4. 2CAPTCHA_API_KEY    — https://2captcha.com   (~2.99$/1K)

    Returns the hCaptcha response token or None on failure.
    Supports up to CAPTCHA_MAX_RETRIES retries per provider.
    """
    import json       as _json
    import urllib.request as _ureq
    import urllib.parse  as _uparse
    import time       as _time

    provider = _get_provider()
    if not provider:
        print("  [captcha] No API key set. Set one of: "
              "CAPSOLVER_API_KEY, ANTI_CAPTCHA_API_KEY, "
              "CAPMONSTER_API_KEY, 2CAPTCHA_API_KEY", flush=True)
        return None

    # Detect proxy type
    proxy_type = "HTTP"
    if proxy.startswith("socks"):
        proxy_type = "SOCKS5"

    def _http_post(url: str, data: dict) -> dict | None:
        try:
            req = _ureq.Request(url, data=_uparse.urlencode(data).encode())
            with _ureq.urlopen(req, timeout=30) as r:
                return _json.loads(r.read())
        except Exception:
            return None

    def _http_get(url: str) -> dict | None:
        try:
            req = _ureq.Request(url)
            with _ureq.urlopen(req, timeout=10) as r:
                return _json.loads(r.read())
        except Exception:
            return None

    # ── Provider: CapSolver ────────────────────────────────────────────────────
    if provider == "capsolver":
        print(f"  [captcha|{provider}] Submitting...", flush=True)
        for attempt in range(1, CAPTCHA_MAX_RETRIES + 1):
            task_payload = {
                "clientKey": CAPTCHA_CAPSOLVER,
                "task": {
                    "type": "HCaptchaTaskProxyless"
                      if not proxy else "HCaptchaTask",
                    "websiteURL": page_url,
                    "websiteKey": site_key,
                },
            }
            if proxy:
                task_payload["task"]["proxy"] = proxy
                task_payload["task"]["proxyType"] = proxy_type

            task_id = _http_post("https://api.capsolver.com/createTask", task_payload)
            if not task_id or task_id.get("errorId"):
                print(f"  [captcha|{provider}] Submit failed (attempt {attempt})", flush=True)
                _time.sleep(3)
                continue

            tid = task_id.get("taskId", "")
            print(f"  [captcha|{provider}] Task ID: {tid}", flush=True)

            for _ in range(90):  # poll up to 90 * 2s = 180s
                _time.sleep(2)
                resp = _http_post("https://api.capsolver.com/getTaskResult",
                                  {"clientKey": CAPTCHA_CAPSOLVER, "taskId": tid})
                if resp and resp.get("status") == "ready":
                    token = resp.get("solution", {}).get("gRecaptchaResponse", "")
                    if token:
                        print(f"  [captcha|{provider}] Solved! Token: {token[:30]}...", flush=True)
                        return token
                if resp and resp.get("status") == "failed":
                    print(f"  [captcha|{provider}] Solve failed (attempt {attempt}), retrying...", flush=True)
                    break
            else:
                print(f"  [captcha|{provider}] Timeout (attempt {attempt}), retrying...", flush=True)
                _time.sleep(5)

        print(f"  [captcha|{provider}] All {CAPTCHA_MAX_RETRIES} attempts failed", flush=True)
        return None

    # ── Provider: Anti-Captcha ─────────────────────────────────────────────────
    elif provider == "anticaptcha":
        print(f"  [captcha|{provider}] Submitting...", flush=True)
        for attempt in range(1, CAPTCHA_MAX_RETRIES + 1):
            create = _http_post("https://api.anti-captcha.com/createTask", {
                "clientKey": CAPTCHA_ANTICAPTCHA,
                "task": {
                    "type": "HCaptchaTaskProxyless"
                      if not proxy else "HCaptchaTask",
                    "websiteURL": page_url,
                    "websiteKey": site_key,
                },
            })
            if not create or create.get("errorId"):
                print(f"  [captcha|{provider}] Submit failed (attempt {attempt})", flush=True)
                _time.sleep(3)
                continue

            tid = create.get("taskId", "")
            for _ in range(90):
                _time.sleep(5)
                resp = _http_get(
                    f"https://api.anti-captcha.com/getTaskResult"
                    f"?clientKey={CAPTCHA_ANTICAPTCHA}&taskId={tid}"
                )
                if resp and resp.get("status") == "ready":
                    token = resp.get("solution", {}).get("gRecaptchaResponse", "")
                    if token:
                        print(f"  [captcha|{provider}] Solved! Token: {token[:30]}...", flush=True)
                        return token
                if resp and resp.get("status") == "failed":
                    print(f"  [captcha|{provider}] Solve failed (attempt {attempt}), retrying...", flush=True)
                    break
            else:
                print(f"  [captcha|{provider}] Timeout (attempt {attempt}), retrying...", flush=True)
                _time.sleep(5)

        print(f"  [captcha|{provider}] All {CAPTCHA_MAX_RETRIES} attempts failed", flush=True)
        return None

    # ── Provider: CapMonster ──────────────────────────────────────────────────
    elif provider == "capmonster":
        print(f"  [captcha|{provider}] Submitting...", flush=True)
        for attempt in range(1, CAPTCHA_MAX_RETRIES + 1):
            create = _http_post("https://api.capmonster.cloud/createTask", {
                "clientKey": CAPTCHA_CAPMONSTER,
                "task": {
                    "type": "HCaptchaTask",
                    "websiteURL": page_url,
                    "websiteKey": site_key,
                    "proxy": proxy,
                    "proxyType": proxy_type,
                } if proxy else {
                    "type": "HCaptchaTaskProxyless",
                    "websiteURL": page_url,
                    "websiteKey": site_key,
                },
            })
            if not create or create.get("errorCode"):
                print(f"  [captcha|{provider}] Submit failed (attempt {attempt})", flush=True)
                _time.sleep(3)
                continue

            tid = create.get("taskId", "")
            for _ in range(90):
                _time.sleep(5)
                resp = _http_post("https://api.capmonster.cloud/getTaskResult", {
                    "clientKey": CAPTCHA_CAPMONSTER,
                    "taskId": tid,
                })
                if resp and resp.get("status") == "ready":
                    token = resp.get("solution", {}).get("gRecaptchaResponse", "")
                    if token:
                        print(f"  [captcha|{provider}] Solved! Token: {token[:30]}...", flush=True)
                        return token
                if resp and resp.get("status") == "failed":
                    print(f"  [captcha|{provider}] Solve failed (attempt {attempt}), retrying...", flush=True)
                    break
            else:
                print(f"  [captcha|{provider}] Timeout (attempt {attempt}), retrying...", flush=True)
                _time.sleep(5)

        print(f"  [captcha|{provider}] All {CAPTCHA_MAX_RETRIES} attempts failed", flush=True)
        return None

    # ── Provider: 2Captcha (default fallback) ─────────────────────────────────
    else:
        def _submit() -> str | None:
            data = {
                "sitekey": site_key,
                "pageurl": page_url,
                "method": "hcaptcha",
                "key": CAPTCHA_2CAPTCHA_KEY,
                "json": "1",
            }
            if proxy:
                data["proxy"] = proxy
                data["proxytype"] = proxy_type
            res = _http_post("http://2captcha.com/in.php", data)
            if res and res.get("status") == 1:
                return res.get("request")
            return None

        def _poll(captcha_id: str) -> str | None:
            for _ in range(120 // CAPTCHA_POLL_DELAY):
                _time.sleep(CAPTCHA_POLL_DELAY)
                res = _http_get(
                    f"http://2captcha.com/res.php"
                    f"?key={CAPTCHA_2CAPTCHA_KEY}&action=get&id={captcha_id}&json=1"
                )
                if res and res.get("status") == 1:
                    return res.get("request")
                err = str(res.get("request", "")) if res else ""
                if err and err not in ("CAPCHA_NOT_READY", ""):
                    return None
            return None

        for attempt in range(1, CAPTCHA_MAX_RETRIES + 1):
            print(f"  [captcha|2captcha] Solving (attempt {attempt}/{CAPTCHA_MAX_RETRIES})...", flush=True)
            captcha_id = _submit()
            if not captcha_id:
                print(f"  [captcha|2captcha] Submit failed, retrying...", flush=True)
                _time.sleep(3)
                continue
            print(f"  [captcha|2captcha] Submitted, ID: {captcha_id}", flush=True)
            token = _poll(captcha_id)
            if token:
                print(f"  [captcha|2captcha] Solved! Token: {token[:30]}...", flush=True)
                return token
            print(f"  [captcha|2captcha] Failed/timeout, retrying...", flush=True)
            _time.sleep(5)

        print(f"  [captcha|2captcha] All {CAPTCHA_MAX_RETRIES} attempts failed", flush=True)
        return None


# ── Cookie session management ───────────────────────────────────────────────────

def save_cookies(cookies: list) -> None:
    """Persist cookies to disk for future re-auth."""
    try:
        COOKIE_SESSION_FILE.write_text(
            _json.dumps(cookies, indent=2),
            encoding="utf-8",
        )
        logger.info(f"  Saved {len(cookies)} cookies")
    except Exception as exc:
        logger.warning(f"  Could not save cookies: {exc}")


def load_cookies() -> Optional[list]:
    if not COOKIE_SESSION_FILE.exists():
        return None
    try:
        data = _json.loads(COOKIE_SESSION_FILE.read_text(encoding="utf-8"))
        return [c for c in data if c.get("value") and c.get("name")] or None
    except Exception:
        return None


# ── Riot client version ─────────────────────────────────────────────────────────

async def _get_riot_version() -> str:
    cache_file = SCRIPT_DIR / "riot_version.json"
    try:
        from datetime import datetime as _dt
        import json as _j
        if cache_file.exists():
            cached = _j.loads(cache_file.read_text(encoding="utf-8"))
            age = (_dt.now() - _dt.fromisoformat(cached["cached_at"])).total_seconds()
            if age < 3600:
                return cached["version"]
    except Exception:
        pass
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://valorant-api.com/v1/version")
            if resp.is_success:
                from datetime import datetime as _dt
                import json as _j
                data = resp.json()["data"]
                build = data["riotClientBuild"]
                version_str = data["riotClientVersion"]
                sdk = version_str.split(".")[1]
                version = f"{sdk}.{build}"
                cache_file.write_text(
                    _j.dumps({"version": version, "cached_at": _dt.now().isoformat()}),
                    encoding="utf-8",
                )
                return version
    except Exception:
        pass
    return "13.05.18.release-13.05-shipping-18-8737475"


# ── Strategy 1: Lockfile ────────────────────────────────────────────────────────

def lockfile_tokens() -> Optional[dict]:
    """Get tokens from local Valorant/Riot Client lockfile."""
    import base64, json as _j, subprocess
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
        port = int(parts[2])
        password = parts[3]
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
        data = _j.loads(result.stdout)
        at = data.get("accessToken", "")
        et = data.get("token", "")
        puuid = data.get("subject", "")
        if not at or not et:
            return None
        return {
            "access_token": at,
            "entitlements_token": et,
            "puuid": puuid,
            "region": "ap",
            "expires_at": 0,
            "refresh_token": "",
        }
    except Exception:
        return None


# ── Strategy 2: Re-auth via cookies (no browser) ────────────────────────────────

async def reauth_with_cookies() -> Optional[dict]:
    """
    Use saved cookies to silently re-authenticate and get fresh access_token.
    No browser needed — uses httpx with the saved session cookies.

    Flow:
      1. Load cookies from riot_session.json
      2. POST to authenticate.riotgames.com with cookies → get login_token
      3. POST to auth.riotgames.com/login-token → Riot session
      4. POST to auth.riotgames.com/authorization → get access_token

    Returns tokens dict or None on failure.
    """
    cookies = load_cookies()
    if not cookies:
        logger.info("  No saved cookie session found")
        return None

    try:
        version = await _get_riot_version()
        sdk = version.split(".")[1] if "." in version else "13.05.18"
    except Exception:
        sdk = "13.05.18"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": f"RiotClient/{sdk} rso-auth (Windows;10;;Professional, x64)",
        "Cache-Control": "no-cache",
    }

    # Build cookie jar
    cookie_jar = {}
    for c in cookies:
        domain = c.get("domain", "")
        name = c.get("name", "")
        value = c.get("value", "")
        if name and value:
            cookie_jar[name] = value

    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            headers=headers,
            cookies=cookie_jar,
        ) as client:

            # Step 1: Use existing session to get new login_token
            r = await client.post(
                "https://authenticate.riotgames.com/api/v1/login",
                json={
                    "clientId": "riot-client",
                    "language": "",
                    "platform": "windows",
                    "remember": False,
                    "riot_identity": {"language": "en_US", "state": "auth"},
                    "sdkVersion": sdk,
                    "type": "auth",
                },
            )

            if not r.is_success:
                logger.info(f"  Cookie re-auth failed: {r.status_code}")
                return None

            data = r.json()

            # If captcha is required, cookies are too old
            if data.get("captcha"):
                logger.info("  Cookies expired — captcha required")
                return None

            login_token = data.get("success", {}).get("login_token", "")
            if not login_token:
                logger.info("  No login_token from cookie session")
                return None

            # Step 2: Exchange login_token for Riot session
            r = await client.post(
                "https://auth.riotgames.com/api/v1/login-token",
                json={
                    "authentication_type": "RiotAuth",
                    "code_verifier": "",
                    "login_token": login_token,
                    "persist_login": False,
                },
            )
            if not r.is_success:
                return None

            # Step 3: Get access_token
            r = await client.post(
                "https://auth.riotgames.com/api/v1/authorization",
                json={
                    "client_id": "riot-client",
                    "nonce": secrets.token_urlsafe(16),
                    "redirect_uri": "http://localhost/redirect",
                    "response_type": "token id_token",
                    "scope": "account openid",
                },
            )
            if not r.is_success:
                return None

            data = r.json()
            uri = data.get("response", {}).get("parameters", {}).get("uri", "")
            if not uri:
                return None

            fragment = uri.split("#", 1)[-1]
            params = {}
            for pair in fragment.split("&"):
                if "=" in pair:
                    k, _, v = pair.partition("=")
                    params[k] = v

            access_token = params.get("access_token", "")
            if not access_token:
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

            user_resp = await client.get(
                "https://auth.riotgames.com/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            puuid = ""
            if user_resp.is_success:
                puuid = user_resp.json().get("sub", "")

            logger.info("  Cookie re-auth successful")
            return {
                "access_token": access_token,
                "entitlements_token": entitlements,
                "puuid": puuid,
                "region": "ap",
                "expires_at": 0,
                "refresh_token": "",
            }

    except Exception as exc:
        logger.info(f"  Cookie re-auth error: {exc}")
        return None


# ── Strategy 3: Headful Playwright login (last resort) ─────────────────────────

def parse_proxy(proxy: str) -> dict | None:
    """
    Parse proxy string to Playwright proxy config.
    Supports formats:
      - http://user:pass@host:port
      - host:port:user:pass (provider format)
      - host:port (no auth)
    Returns Playwright proxy dict or None.
    """
    proxy = proxy.strip()
    if not proxy:
        return None

    # host:port:user:pass format (provider format) - parse before scheme check
    if not proxy.startswith("http://") and not proxy.startswith("https://") and proxy.count(":") >= 3:
        parts = proxy.split(":")
        if len(parts) >= 4:
            host = parts[0]
            port = parts[1]
            user = parts[2]
            pwd = ":".join(parts[3:])
            return {
                "server": f"http://{host}:{port}",
                "username": user,
                "password": pwd
            }

    # Already has scheme - extract credentials if present
    if proxy.startswith("http://") or proxy.startswith("https://"):
        # Try to extract user:pass@host:port from URL
        parsed = proxy.replace("http://", "").replace("https://", "")
        if "@" in parsed:
            creds, rest = parsed.split("@", 1)
            if ":" in creds:
                user, pwd = creds.split(":", 1)
                return {
                    "server": f"http://{rest}",
                    "username": user,
                    "password": pwd
                }
        return {"server": proxy}

    # host:port format (no auth)
    return {"server": f"http://{proxy}"}


async def _headful_login(username: str, password: str, proxy: str = "", headless: bool = False) -> Optional[dict]:
    """
    Playwright with shared Chromium instance — NOT detected as automation.
    Opens a real Chrome window, user logs in once, tokens are saved.
    Supports HTTPS/SOCKS5 proxy per context.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("  playwright not installed")
        return None

    pw_proxy = parse_proxy(proxy)
    proxy_short = proxy.split("@")[-1] if "@" in proxy else proxy
    logger.info(f"  [browser] using shared Chromium (headless={headless}) proxy={proxy_short}")

    try:
        browser = await _get_shared_browser(headless)

        context = await browser.new_context(
            proxy=pw_proxy,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        # Navigate to Riot auth
        await page.goto(
            "https://auth.riotgames.com/authorize"
            "?redirect_uri=http://localhost/redirect"
            "&client_id=riot-client"
            "&response_type=token%20id_token"
            "&nonce=1"
            "&scope=openid%20link%20ban%20lol_region%20account",
            wait_until="domcontentloaded",
            timeout=45_000,
        )

        # Wait for username field
        try:
            await page.wait_for_selector('input[name="username"]', timeout=30_000)
        except Exception:
            if await _is_blocked(page):
                await context.close()
                return None
            await context.close()
            return None

        await asyncio.sleep(1.5)

        # Fill username
        if not await _fill_input(page, 'input[name="username"]', username):
            await context.close()
            return None
        await page.keyboard.press("Enter")
        await asyncio.sleep(2)

        if await _is_magic_link(page):
            logger.info("  Magic link not supported — check email manually")
            await context.close()
            return None

        # Wait for password
        try:
            await page.wait_for_selector('input[name="password"]', timeout=20_000)
        except Exception:
            await context.close()
            return None

        # Fill password
        if not await _fill_input(page, 'input[name="password"]', password):
            await context.close()
            return None

        await asyncio.sleep(0.5)
        await _click_sign_in(page)
        logger.info("  Waiting for redirect...")

        # Wait for redirect with token — detect & auto-solve hCaptcha
        captcha_solved = False
        for attempt in range(80):  # 80 * 0.5s = 40s max
            await asyncio.sleep(0.5)

            if await _is_blocked(page):
                logger.info(f"  [debug] blocked on attempt {attempt}")
                await context.close()
                return None

            url = page.url

            # Check for hCaptcha challenge page
            if "hcaptcha" in url.lower() or "challenges" in url.lower():
                if not captcha_solved:
                    captcha_info = await _is_hcaptcha_on_page(page)
                    if captcha_info:
                        proxy_short2 = proxy.split("@")[-1] if "@" in proxy else proxy
                        token = await _solve_hcaptcha(
                            captcha_info["site_key"],
                            captcha_info["page_url"],
                            proxy=proxy_short2,
                        )
                        if token:
                            await page.evaluate(
                                f'document.querySelector("[name=h-captcha-response]")'
                                f'?.setAttribute("value", "{token}");'
                                f'document.querySelector("[data-hcaptcha-response]")'
                                f'?.setAttribute("data-hcaptcha-response", "{token}");'
                            )
                            try:
                                submitted = False
                                for frame in page.frames:
                                    try:
                                        submit = await frame.query_selector(
                                            '#challenge-form button[type="submit"], '
                                            '#hcaptcha-popup a, '
                                            'button[data-hcaptcha-response]'
                                        )
                                        if submit and not submitted:
                                            await submit.click()
                                            submitted = True
                                    except Exception:
                                        pass
                                if not submitted:
                                    await page.evaluate(
                                        'document.querySelectorAll("button")[0]?.click()'
                                    )
                            except Exception:
                                pass
                            captcha_solved = True
                            logger.info("  [captcha] Token submitted, waiting for redirect...")
                            await asyncio.sleep(2)
                        else:
                            logger.warning("  [captcha] Auto-solve failed, captcha page detected")
                            await context.close()
                            return None
                    else:
                        logger.warning("  [captcha] hCaptcha detected but no sitekey found")
                        await context.close()
                        return None

            if "access_token=" in url:
                logger.info(f"  [debug] redirect reached: {url[:80]}...")
                break

            # Log every ~10s
            if attempt % 4 == 0:
                logger.info(f"  [debug] still waiting... (attempt {attempt}, url={url[:80]})")
        else:
            logger.info(f"  [debug] timeout waiting for redirect, final url: {page.url[:200]}")
            await _take_ss(page, "no_redirect", username)
            await context.close()
            return None

        # Parse token from URL fragment
        fragment = url.split("#", 1)[-1]
        params = {}
        for pair in fragment.split("&"):
            if "=" in pair:
                k, _, v = pair.partition("=")
                params[k] = v

        access_token = params.get("access_token", "")
        if not access_token:
            await context.close()
            return None

        # Save cookies for future runs
        cookies = await context.cookies()
        save_cookies(cookies)

        logger.info("  Headful login successful — tokens saved")

        # Get entitlements — use the same proxy the browser used
        # BUG FIX (Bug 3): previously no proxy was used here, causing
        # inconsistent IP and potential captcha triggers from Riot.
        import httpx
        auth_hdr = {"Authorization": f"Bearer {access_token}"}
        proxies = {"http://": proxy, "https://": proxy} if proxy else {}
        async with httpx.AsyncClient(timeout=10.0, proxies=proxies) as client:
            ent_resp = await client.post(
                "https://entitlements.auth.riotgames.com/api/token/v1",
                headers=auth_hdr, json={},
            )
            entitlements = ""
            if ent_resp.is_success:
                entitlements = ent_resp.json().get("entitlements_token", "")

            user_resp = await client.get(
                "https://auth.riotgames.com/userinfo",
                headers=auth_hdr,
            )
            puuid = ""
            if user_resp.is_success:
                puuid = user_resp.json().get("sub", "")

        await context.close()
        return {
            "access_token": access_token,
            "entitlements_token": entitlements,
            "puuid": puuid,
            "region": "ap",
            "expires_at": 0,
            "refresh_token": "",
        }

    except Exception as exc:
        logger.error(f"  Headful login error: {exc}")
        return None


# ── Public API ─────────────────────────────────────────────────────────────────

async def get_tokens(username: str, password: str, proxy: str = "", headless: bool = False) -> Optional[dict]:
    """
    Get valid tokens for an account using the best available strategy.

    Strategy:
      1. Lockfile → instant (Valorant running)
      2. Saved cookies → silent re-auth (no browser)
      3. Headful Playwright → browser with proxy, cookies saved for next runs

    Returns tokens dict or None.
    """
    # Strategy 1: Lockfile
    tokens = lockfile_tokens()
    if tokens:
        logger.info("  Auth: lockfile")
        return tokens

    # Strategy 2: Cookie re-auth
    logger.info("  Auth: trying cookie session...")
    tokens = await reauth_with_cookies()
    if tokens:
        return tokens

    # Strategy 3: Headful login with proxy
    proxy_label = proxy.split('@')[-1] if proxy else 'direct'
    mode_label = "headless" if headless else "headful"
    logger.info(f"  Auth: {mode_label} Chrome for {username} (proxy: {proxy_label})...")
    tokens = await _headful_login(username, password, proxy, headless)
    if tokens:
        return tokens

    logger.warning("  Auth: all methods failed")
    return None


# ── Simple HTTP refresh (for accounts.json compatibility) ──────────────────────

async def refresh_access_token(refresh_token: str) -> Optional[dict]:
    """Riot-client flow does not support refresh_token. Returns None."""
    return None
