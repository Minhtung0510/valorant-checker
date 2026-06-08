"""
riot_cookie_extractor.py

Cach lay token: ban mo trinh duyet thu cong 1 lan,
export cookies → file json → script doc vao.

Huong dan:
  1. cai cookie-editor:
       Chrome:  https://chrome.google.com/webstore/detail/cookie-editor/      (tim "EditThisCookie")
       Edge:    https://microsoftedge.microsoft.com/addons/ (tim "Cookie Editor")
       Firefox: https://addons.mozilla.org/en-US/firefox/addon/cookie-editor/

  2. Mo trinh duyet, dang nhap tai auth.riotgames.com
       → Dung may tinh 1 lan thoi

  3. Tai auth.riotgames.com, mo Cookie Editor
       → Bam "Export" → Luu JSON

  4. Chay:  python riot_cookie_extractor.py cookies.json

  5. Script se:
       - Doc cookies
       - Lay access_token + refresh_token
       - Luu vao accounts.json

  Sau do checker.py se doc tu accounts.json, khong can trinh duyet nua.
"""
import asyncio
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
OUTPUT_FILE = PROJECT_DIR / "accounts.json"


def parse_cookie_value(val: str) -> str:
    """Unicode decode for Riot cookies."""
    try:
        return val.encode("utf-8").decode("unicode_escape")
    except Exception:
        return val


async def exchange_cookies_for_tokens(cookies: list[dict]) -> dict | None:
    """
    Dung Riot client API (httpx) de lay tokens tu cookies.
    Khong can trinh duyet.
    """
    import httpx

    cookie_str = "; ".join(
        f"{c['name']}={c['value']}" for c in cookies if c.get("value")
    )

    headers = {
        "Cookie": cookie_str,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://auth.riotgames.com/",
    }

    try:
        # Thu 1: goi /userinfo de xem cookies co valid khong
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://auth.riotgames.com/userinfo",
                headers=headers,
                follow_redirects=True,
            )
            print(f"  /userinfo status: {resp.status_code}")

            if resp.status_code == 401:
                print("  Cookies khong con valid → can export lai tu trinh duyet")
                return None

            if resp.status_code != 200:
                print(f"  Response: {resp.text[:200]}")
                return None

            userinfo = resp.json()
            print(f"  Username: {userinfo.get('username', userinfo.get('sub', '?'))}")

            # Lay entitlements
            resp2 = await client.post(
                "https://entitlements.auth.riotgames.com/api/token/v1",
                headers={**headers, "Content-Type": "application/json"},
                json={},
            )
            entitlements = ""
            if resp2.is_success:
                entitlements = resp2.json().get("entitlements_token", "")
                print(f"  Entitlements: OK ({len(entitlements)} chars)")

            return {
                "userinfo":      userinfo,
                "entitlements":  entitlements,
                "cookies":       cookies,
            }

    except Exception as e:
        print(f"  Error: {e}")
        return None


async def get_tokens_via_code_flow() -> dict | None:
    """
    Neu cookies khong work, cho nguoi dung nhap auth_code thu cong.

    Cach lay auth_code:
      1. Mo trinh duyet thu cong → auth.riotgames.com
      2. Dang nhap thanh cong
      3. Copy URL sau khi redirect (co ?code=xxx)
    """
    import httpx

    auth_url = (
        "https://auth.riotgames.com/authorize"
        "?redirect_uri=http://localhost/riot-community-callback"
        "&client_id=riot-client"
        "&response_type=code"
        "&nonce=1"
        "&scope=openid%20link%20ban%20lol_region%20account"
    )
    print()
    print("=" * 60)
    print("CACH LAY AUTH CODE (neu cookies khong work):")
    print("=" * 60)
    print("  1. Mo trinh duyet (Chrome/Edge):")
    print(f"     {auth_url}")
    print("  2. Dang nhap → redirect se that bai (localhost)")
    print("  3. Copy URL tu thanh dia chi (co ?code=...)")
    print("  4. Paste o duoi:")
    print("=" * 60)
    print()

    code = input("Paste redirect URL hoac auth code (Enter de thoat): ").strip()
    if not code:
        return None

    if "code=" in code:
        from urllib.parse import parse_qs, urlparse
        params = parse_qs(urlparse(code).query)
        code = (params.get("code") or [""])[0]

    if not code:
        print("  Khong tim thay code")
        return None

    # Exchange code for tokens
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://auth.riotgames.com/api/v1/authorization",
                json={
                    "code":          code,
                    "client_id":     "riot-client",
                    "grant_type":    "authorization_code",
                    "redirect_uri":  "http://localhost/riot-community-callback",
                },
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            if not resp.is_success:
                print(f"  Exchange failed: {resp.status_code} {resp.text[:200]}")
                return None
            data = resp.json()
            return {
                "access_token":  data.get("access_token", ""),
                "refresh_token": data.get("refresh_token", ""),
                "expires_in":   data.get("expires_in", 3600),
                "id_token":     data.get("id_token", ""),
            }
    except Exception as e:
        print(f"  Error: {e}")
        return None


async def interactive_flow():
    """Cho nguoi dung chon cach nhap token."""
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║      RIOT TOKEN SETUP — Lay refresh_token cho bot       ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()
    print("Chon cach lay token:")
    print("  [1] Export cookies tu trinh duyet (chua co -> chon 2)")
    print("  [2] Lay auth_code thu cong (recommended)")
    print()
    choice = input("Chon (1/2): ").strip()

    if choice == "1":
        cookie_file = input("Duong dan file cookies (.json): ").strip().strip('"')
        if not cookie_file:
            return

        path = Path(cookie_file)
        if not path.exists():
            print(f"  File khong ton tai: {cookie_file}")
            return

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            # Normalize: co the la dict {cookies:[...]} hoac list
            if isinstance(raw, dict):
                cookies = raw.get("cookies", list(raw.values())[0] if raw else [])
            else:
                cookies = raw
            if not cookies:
                print("  Khong tim thay cookies trong file")
                return
        except Exception as e:
            print(f"  Loi doc file: {e}")
            return

        print(f"  Doc duoc {len(cookies)} cookies")
        result = await exchange_cookies_for_tokens(cookies)
        if not result:
            return

        userinfo = result["userinfo"]
        entitlements = result["entitlements"]

        # Doc refresh_token tu cookies
        refresh_token = next(
            (c["value"] for c in cookies if "riot" in c.get("name","").lower() and "refresh" in c.get("name","").lower()),
            ""
        )
        access_token = next(
            (c["value"] for c in cookies if "riot" in c.get("name","").lower() and "access" in c.get("name","").lower()),
            ""
        )

        # Luu vao accounts.json
        username = userinfo.get("username") or input("Nhap username (email): ").strip()
        if not username:
            print("  Huy")
            return

        region = input("Region (ap/br/ea/eu/kr/latam/na) [default: ap]: ").strip() or "ap"

        _save_tokens(username, region, {
            "access_token":        access_token,
            "refresh_token":       refresh_token,
            "entitlements_token":  entitlements,
            "puuid":               userinfo.get("sub", ""),
            "expires_at":          0,  # se duoc cap nhat khi refresh
        })
        print(f"  Da luu tokens cho {username}")

    else:
        tokens = await get_tokens_via_code_flow()
        if not tokens:
            print("  Loi lay tokens")
            return

        username = input("Nhap username (email): ").strip()
        if not username:
            print("  Huy")
            return
        region = input("Region (ap/br/ea/eu/kr/latam/na) [default: ap]: ").strip() or "ap"

        # Lay entitlements
        import httpx
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        entitlements = ""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://entitlements.auth.riotgames.com/api/token/v1",
                    headers={**headers, "Content-Type": "application/json"},
                    json={},
                )
                if resp.is_success:
                    entitlements = resp.json().get("entitlements_token", "")
        except Exception as e:
            print(f"  Entitlements error: {e}")

        resp2 = await httpx.AsyncClient(timeout=10).get(
            "https://auth.riotgames.com/userinfo",
            headers=headers,
        )
        puuid = ""
        if resp2.is_success:
            puuid = resp2.json().get("sub", "")

        _save_tokens(username, region, {
            "access_token":        tokens["access_token"],
            "refresh_token":       tokens["refresh_token"],
            "entitlements_token":  entitlements,
            "puuid":               puuid,
            "expires_at":          0,
        })
        print(f"  Da luu tokens cho {username} ✓")
        print()
        print("  Gio co the xoa file cookies.json (khong can nua).")
        print("  refresh_token da luu — check tiep theo se tu dong refresh.")


def _save_tokens(username: str, region: str, tokens: dict):
    accounts_file = PROJECT_DIR / "accounts.json"
    data = {}
    if accounts_file.exists():
        try:
            data = json.loads(accounts_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    key = username.lower()
    data[key] = {
        "username": username,
        "region":   region,
        "tokens": tokens,
    }

    accounts_file.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    asyncio.run(interactive_flow())
