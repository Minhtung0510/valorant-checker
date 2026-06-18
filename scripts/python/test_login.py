#!/usr/bin/env python3
"""
Valorant Account Checker - Manual Login Flow
1. Mở trình duyệt đến trang login Riot
2. User tự login + giải captcha
3. User bấm Enter khi xong → script lấy URL → call API → trả kết quả
"""

import os
import sys
import json
import time
import socket
import threading
import subprocess
import requests
import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import List, Optional

# ============== CONFIG ==============
CONCURRENCY = int(os.getenv("CONCURRENCY", "3"))
ACCOUNTS_FILE = "accounts.txt"
PROXIES_FILE = "proxies.txt"
BASE_OUTPUT_DIR = r"C:\Users\WORK\Desktop\Check-done"
LOGS_DIR = "logs"

ORBITA_BROWSER_PATH = r"C:\Users\WORK\Downloads\Gologin\All-Browsers\orbita-browser-145\chrome.exe"

RIOT_AUTH_URL = (
    "https://auth.riotgames.com/authorize"
    "?redirect_uri=http://localhost/redirect"
    "&client_id=riot-client"
    "&response_type=token%20id_token"
    "&nonce=1"
    "&scope=openid%20link%20ban%20lol_region%20account"
)

RIOT_USER_URL = "https://auth.riotgames.com/v1/userinfo"
RIOT_ENTITLEMENTS_URL = "https://entitlements.token.riotgames.com/api/token/v1"


@dataclass
class ProxyInfo:
    """Thông tin proxy đã parse từ proxies.txt."""
    host: str
    port: int
    username: str = ""
    password: str = ""
    
    @property
    def server(self) -> str:
        """host:port cho --proxy-server flag của Chrome."""
        return f"{self.host}:{self.port}"
    
    @property
    def http_url(self) -> str:
        """URL đầy đủ cho requests client."""
        if self.username and self.password:
            return f"http://{self.username}:{self.password}@{self.host}:{self.port}"
        return f"http://{self.host}:{self.port}"
    
    @staticmethod
    def parse(line: str) -> Optional["ProxyInfo"]:
        """Parse 1 dòng từ proxies.txt."""
        line = line.strip()
        if not line or line.startswith("#"):
            return None
        parts = line.split(":")
        if len(parts) < 2:
            return None
        try:
            return ProxyInfo(
                host=parts[0],
                port=int(parts[1]),
                username=parts[2] if len(parts) > 2 else "",
                password=parts[3] if len(parts) > 3 else "",
            )
        except (ValueError, IndexError):
            return None


def load_proxies() -> List[ProxyInfo]:
    if not os.path.exists(PROXIES_FILE):
        return []
    proxies = []
    with open(PROXIES_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            p = ProxyInfo.parse(line)
            if p:
                proxies.append(p)
    return proxies


@dataclass
class AccountInfo:
    username: str = ""
    password: str = ""
    status: str = "pending"
    access_token: str = ""
    id_token: str = ""
    entitlement: str = ""
    region: str = ""
    country: str = ""
    skins_count: int = 0
    rank: str = "Unknown"
    error: str = ""
    elapsed: float = 0
    redirect_url: str = ""
    proxy: Optional[ProxyInfo] = None


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def load_accounts() -> List[AccountInfo]:
    accounts = []
    with open(ACCOUNTS_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if ':' in line and not line.startswith('#'):
                username, password = line.split(':', 1)
                accounts.append(AccountInfo(username=username, password=password))
    return accounts


def parse_tokens(url: str) -> dict:
    """Parse tokens from redirect URL hash"""
    tokens = {}
    try:
        if '#' not in url:
            return tokens
        fragment = url.split('#', 1)[1]
        for pair in fragment.split('&'):
            if '=' in pair:
                k, _, v = pair.partition('=')
                tokens[k] = v
    except:
        pass
    return tokens


def check_api(access_token: str, redirect_url: str = "", proxy_info: Optional[ProxyInfo] = None) -> Optional[dict]:
    """Call Riot API - same as webapp"""
    result = {
        "valid": False,
        "region": "sea",
        "country": "",
        "entitlement": "",
        "skins_count": 0,
        "rank": "Unknown",
        "error": ""
    }
    
    proxies_dict = {}
    if proxy_info:
        proxies_dict = {
            "http": proxy_info.http_url,
            "https": proxy_info.http_url
        }
    
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Step 1: Get user info
        resp = requests.get(RIOT_USER_URL, headers=headers, proxies=proxies_dict, timeout=15)
        if not resp.ok:
            result["error"] = f"userinfo failed: {resp.status_code}"
            return result
        
        user_data = resp.json()
        result["region"] = user_data.get("lo_region", user_data.get("region", "sea"))
        result["country"] = user_data.get("country", "unknown")
        puuid = user_data.get("sub", "")
        print(f"    [*] Userinfo OK: region={result['region']}, country={result['country']}")
        
        # Step 2: Get entitlement
        ent_headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        ent_resp = requests.post(RIOT_ENTITLEMENTS_URL, headers=ent_headers, json={}, proxies=proxies_dict, timeout=15)
        if not ent_resp.ok:
            result["error"] = f"entitlement failed: {ent_resp.status_code}"
            return result
        
        result["entitlement"] = ent_resp.json().get("entitlements_token", "")
        print(f"    [*] Entitlement OK")
        
        # Step 3: Get skins
        region_prefix_map = {
            "sea": "pdsea", "ap": "pdap", "kr": "pdkr",
            "eu": "europe", "na": "pdnne", "pbe": "pdpbe"
        }
        region_prefix = region_prefix_map.get(result["region"].lower(), "pdsea")
        
        if puuid:
            store_headers = {
                "Authorization": f"Bearer {access_token}",
                "X-Riot-Entitlements-JWT": result["entitlement"]
            }
            store_url = f"https://{region_prefix}.a.pvp.net/store/v2/storefront/{puuid}"
            store_resp = requests.get(store_url, headers=store_headers, proxies=proxies_dict, timeout=15)
            if store_resp.ok:
                store_data = store_resp.json()
                if "SkinsPanelLayout" in store_data:
                    offers = store_data["SkinsPanelLayout"].get("SingleItemOffers", [])
                    result["skins_count"] = len(offers)
                    print(f"    [*] Skins: {result['skins_count']}")
        
        # Step 4: Get rank
        if puuid:
            mmr_headers = {
                "Authorization": f"Bearer {access_token}",
                "X-Riot-Entitlements-JWT": result["entitlement"]
            }
            mmr_url = f"https://{region_prefix}.a.pvp.net/mmr/v1/players/{puuid}"
            mmr_resp = requests.get(mmr_url, headers=mmr_headers, proxies=proxies_dict, timeout=15)
            if mmr_resp.ok:
                mmr_data = mmr_resp.json()
                if "queue_map" in mmr_data:
                    for queue in ["competitive", "unrated", "spike_rush"]:
                        if queue in mmr_data["queue_map"]:
                            tier = mmr_data["queue_map"][queue].get("seasonal_info", {}).get("tier", 0)
                            if tier > 0:
                                result["rank"] = str(tier)
                                break
            print(f"    [*] Rank: {result['rank']}")
        
        result["valid"] = True
        return result
        
    except Exception as e:
        result["error"] = str(e)
        return result


def launch_orbita_browser(port: int, user_data_dir: str, proxy: Optional[ProxyInfo] = None) -> subprocess.Popen:
    user_data_dir = os.path.abspath(user_data_dir)
    args = [
        ORBITA_BROWSER_PATH,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-popup-blocking",
        "--disable-notifications",
        "--disable-infobars",
        "--window-size=1280,720",
        "--lang=en-US",
    ]
    args.append("--disable-extensions")
    if proxy:
        args.append(f"--proxy-server={proxy.server}")
    os.makedirs(user_data_dir, exist_ok=True)
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    time.sleep(3)
    return proc


def check_single_account(result: AccountInfo, thread_id: int, lock: threading.Lock, progress: dict):
    """Check single account - user manually logs in, script captures URL and calls API"""
    from playwright.sync_api import sync_playwright
    
    start_time = time.time()
    browser_proc = None
    port = find_free_port()
    user_data_dir = f"profiles/{result.username}_{int(time.time())}"
    
    try:
        print(f"\n  === Thread-{thread_id}: {result.username} ===")
        proxy_desc = f" via proxy {result.proxy.server}" if result.proxy else ""
        print(f"  [Thread-{thread_id}] Launching Orbita on port {port}{proxy_desc}...")
        browser_proc = launch_orbita_browser(port, user_data_dir, proxy=result.proxy)
        time.sleep(2)
        
        with sync_playwright() as p:
            cdp_url = f"http://localhost:{port}"
            
            for attempt in range(5):
                try:
                    browser = p.chromium.connect_over_cdp(cdp_url)
                    break
                except:
                    if attempt < 4:
                        time.sleep(2)
                    else:
                        raise
            
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.new_page()
            
            # Setup proxy authentication nếu có proxy với credentials
            cdp_session = None
            if result.proxy and result.proxy.username:
                try:
                    cdp_session = context.new_cdp_session(page)
                    cdp_session.send("Fetch.enable", {"handleAuthRequests": True})
                    
                    proxy = result.proxy
                    
                    def on_auth_required(params):
                        try:
                            cdp_session.send("Fetch.continueWithAuth", {
                                "requestId": params["requestId"],
                                "authChallengeResponse": {
                                    "response": "ProvideCredentials",
                                    "username": proxy.username,
                                    "password": proxy.password,
                                }
                            })
                        except Exception as e:
                            print(f"  [Thread-{thread_id}] Proxy auth continuation failed: {e}")
                    
                    cdp_session.on("Fetch.authRequired", on_auth_required)
                    print(f"  [Thread-{thread_id}] Proxy auth handler ready for {proxy.server}")
                except Exception as e:
                    print(f"  [Thread-{thread_id}] Proxy auth setup failed: {e}")
            
            # Navigate to Riot login
            print(f"  [Thread-{thread_id}] Opening Riot login page...")
            page.goto(RIOT_AUTH_URL, wait_until='load', timeout=30000)
            time.sleep(1)
            
            # Pre-fill username/password in background
            try:
                time.sleep(2)
                
                # Fill username if visible
                for sel in ['input[name="username"]', 'input[name="email"]', 'input[type="text"]']:
                    try:
                        el = page.wait_for_selector(sel, timeout=3000)
                        if el:
                            el.fill(result.username)
                            print(f"  [Thread-{thread_id}] Filled username: {result.username}")
                            page.keyboard.press("Enter")
                            time.sleep(2)
                            break
                    except:
                        continue
                
                # Fill password if visible
                for sel in ['input[name="password"]', 'input[type="password"]']:
                    try:
                        el = page.wait_for_selector(sel, timeout=3000)
                        if el:
                            el.fill(result.password)
                            print(f"  [Thread-{thread_id}] Filled password")
                            page.keyboard.press("Enter")
                            time.sleep(2)
                            break
                    except:
                        continue
                        
            except Exception as e:
                print(f"  [Thread-{thread_id}] Auto-fill skipped: {e}")
            
            # Prompt user to handle captcha and login
            print(f"\n  >>> Thread-{thread_id}: {result.username} <<<")
            print(f"  >>> Solve captcha & login manually, then press ENTER in terminal <<<")
            print(f"  >>> Waiting for redirect to localhost/redirect... <<<\n")
            
            # Wait for redirect to localhost/redirect
            login_success = False
            redirect_url = ""
            captured_url = {"value": ""}

            # ── Dùng framenavigated thay vì on("request") ────────────────
            # connect_over_cdp không fire "request" event cho navigation
            # nhưng "framenavigated" fire ngay khi URL thay đổi,
            # kể cả khi page bị ERR_CONNECTION_REFUSED
            def on_navigated(frame):
                if frame == page.main_frame:
                    url = frame.url
                    if "localhost/redirect" in url and "access_token=" in url:
                        captured_url["value"] = url

            page.on("framenavigated", on_navigated)

            for i in range(120):  # Wait up to 2 minutes
                time.sleep(1)

                # Ưu tiên URL đã bắt được qua framenavigated
                if captured_url["value"]:
                    redirect_url = captured_url["value"]
                    print(f"  [Thread-{thread_id}] Token captured via framenavigated!")
                    print(f"  [Thread-{thread_id}] URL: {redirect_url[:100]}...")
                    break

                try:
                    current_url = page.url

                    # Fallback: poll page.url trực tiếp (KHÔNG dùng page.evaluate)
                    if "localhost/redirect" in current_url and "access_token=" in current_url:
                        print(f"  [Thread-{thread_id}] Token captured via page.url fallback!")
                        redirect_url = current_url
                        print(f"  [Thread-{thread_id}] URL: {redirect_url[:100]}...")
                        break

                    # Chỉ bail out khi Riot trả lỗi rõ ràng
                    # KHÔNG check "error" chung chung → false positive với ERR_CONNECTION_REFUSED
                    if any(k in current_url for k in ["error=access_denied", "error=login_required", "/login?error"]):
                        print(f"  [Thread-{thread_id}] Auth denied: {current_url[:100]}")
                        redirect_url = current_url
                        break

                except:
                    pass

                if i % 15 == 0 and i > 0:
                    try:
                        print(f"  [Thread-{thread_id}] Still waiting... ({i}s) URL: {page.url[:60]}")
                    except:
                        print(f"  [Thread-{thread_id}] Still waiting... ({i}s)")
            
            if cdp_session:
                try:
                    cdp_session.detach()
                except:
                    pass
            browser.close()
            
            # Parse tokens from URL
            tokens = parse_tokens(redirect_url)
            if tokens.get("access_token"):
                result.access_token = tokens.get("access_token", "")
                result.id_token = tokens.get("id_token", "")
                result.redirect_url = redirect_url
                result.status = "live"
                print(f"  [Thread-{thread_id}] Token captured! Calling API...")
                
                # Call API like webapp
                api_result = check_api(result.access_token, redirect_url, proxy_info=result.proxy)
                
                if api_result and api_result.get("valid"):
                    result.entitlement = api_result["entitlement"]
                    result.region = api_result["region"]
                    result.country = api_result["country"]
                    result.skins_count = api_result["skins_count"]
                    result.rank = api_result["rank"]
                    result.status = "live"
                    print(f"  [Thread-{thread_id}] >>> SUCCESS: {result.skins_count} skins | Rank {result.rank} | {result.region.upper()} | {result.country}")
                else:
                    result.status = "api_error"
                    result.error = api_result.get("error", "unknown") if api_result else "unknown"
                    print(f"  [Thread-{thread_id}] API failed: {result.error}")
            else:
                result.status = "timeout"
                result.error = "No redirect detected"
                result.redirect_url = redirect_url
                print(f"  [Thread-{thread_id}] No token in URL - might be wrong password or timeout")
                try:
                    page.screenshot(path=f"{LOGS_DIR}/screenshots/{result.username}_no_token.png")
                except:
                    pass
    
    except Exception as e:
        result.status = "error"
        result.error = str(e)
        print(f"  [Thread-{thread_id}] ERROR: {e}")
    
    finally:
        if browser_proc:
            try:
                browser_proc.terminate()
                browser_proc.wait(timeout=5)
            except:
                browser_proc.kill()
        try:
            if os.path.exists(user_data_dir):
                shutil.rmtree(user_data_dir, ignore_errors=True)
        except:
            pass
    
    result.elapsed = time.time() - start_time
    save_to_folder(result)
    
    with lock:
        progress['done'] += 1
        status_icon = {
            "live": "[LIVE]", "wrong_password": "[WRONG-PW]", "wrong_username": "[WRONG-USER]",
            "locked": "[LOCKED]", "banned": "[BANNED]", "error": "[ERROR]", "timeout": "[TIMEOUT]",
            "api_error": "[API-ERR]"
        }.get(result.status, "[??]")
        print(f"\n[{progress['done']}/{progress['total']}] Thread-{thread_id} | {result.username}: {status_icon} | {result.skins_count} skins | Rank {result.rank} | {result.elapsed:.1f}s")


def save_to_folder(result: AccountInfo):
    try:
        folder_name = f"{result.skins_count}_Skins" if result.status == "live" else {
            "wrong_password": "Wrong_Password", "wrong_username": "Wrong_Username",
            "locked": "Locked_Account", "banned": "Banned_Account",
            "error": "Error_Accounts", "timeout": "Timeout_Accounts", "api_error": "API_Error"
        }.get(result.status, "Other")
        
        folder_path = os.path.join(BASE_OUTPUT_DIR, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        
        safe_name = result.username.replace("/", "_").replace("\\", "_").replace(":", "_")
        filename = os.path.join(folder_path, f"{safe_name}.txt")
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"=== VALORANT ACCOUNT INFO ===\n\n")
            f.write(f"Username: {result.username}\n")
            f.write(f"Password: {result.password}\n")
            f.write(f"Status: {result.status.upper()}\n")
            if result.status == "live":
                f.write(f"\n--- Account Details ---\n")
                f.write(f"Skins Count: {result.skins_count}\n")
                f.write(f"Rank: {result.rank}\n")
                f.write(f"Region: {result.region}\n")
                f.write(f"Country: {result.country}\n")
            if result.error:
                f.write(f"\nError: {result.error}\n")
            if result.redirect_url:
                f.write(f"\nRedirect URL: {result.redirect_url}\n")
    
    except Exception as e:
        print(f"  [!] Save failed for {result.username}: {e}")


def run_checker():
    print("=" * 60)
    print("  VALORANT ACCOUNT CHECKER")
    print("  Flow: Auto-fill login -> Manual captcha/login -> API")
    print("=" * 60)
    print(f"  Browser: {ORBITA_BROWSER_PATH}")
    print(f"  Concurrency: {CONCURRENCY} threads")
    print("=" * 60)
    
    os.makedirs(f"{LOGS_DIR}/screenshots", exist_ok=True)
    os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)
    os.makedirs("profiles", exist_ok=True)
    
    accounts = load_accounts()
    print(f"\n[*] Loaded {len(accounts)} accounts\n")
    
    if not accounts:
        print("[!] No accounts found!")
        return
        
    proxies = load_proxies()
    if proxies:
        print(f"[*] Loaded {len(proxies)} proxies from {PROXIES_FILE}")
        for i, acc in enumerate(accounts):
            acc.proxy = proxies[i % len(proxies)]
    else:
        print("[!] No proxies loaded - all accounts will run direct")
    
    if not os.path.exists(ORBITA_BROWSER_PATH):
        print(f"[!] Orbita browser not found at:\n    {ORBITA_BROWSER_PATH}")
        return
    
    lock = threading.Lock()
    progress = {'done': 0, 'total': len(accounts)}
    
    print(f"[*] Starting {CONCURRENCY} threads...\n")
    print("-" * 60)
    
    start_total = time.time()
    
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = []
        for i, acc in enumerate(accounts):
            future = executor.submit(check_single_account, acc, i + 1, lock, progress)
            futures.append((future, acc))
        
        for future, acc in futures:
            future.result()
    
    total_time = time.time() - start_total
    
    results = [f[1] for f in futures]
    with open(f"{LOGS_DIR}/results.json", 'w') as f:
        json.dump([{
            'username': r.username, 'password': r.password, 'status': r.status,
            'skins_count': r.skins_count, 'rank': r.rank, 'region': r.region,
            'country': r.country, 'error': r.error, 'redirect_url': r.redirect_url
        } for r in results], f, indent=2, ensure_ascii=False)
    
    by_status = {}
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    
    print("\n" + "=" * 60)
    print("  RESULTS SUMMARY")
    print("=" * 60)
    for r in results:
        icon = {"live": "LIVE", "wrong_password": "WRONG-PW", "wrong_username": "WRONG-USER",
                "locked": "LOCKED", "banned": "BANNED", "error": "ERROR", "timeout": "TIMEOUT",
                "api_error": "API-ERR"}.get(r.status, "??")
        print(f"  [{icon:10}] {r.username:20} | {r.skins_count:4} skins | Rank {r.rank:4} | {r.region.upper()}")
    
    print(f"\n  Total time: {total_time:.1f}s")
    print(f"\n[*] Details: {LOGS_DIR}/results.json")
    print(f"[*] Folders: {BASE_OUTPUT_DIR}")
    
    try:
        shutil.rmtree("profiles", ignore_errors=True)
    except:
        pass


if __name__ == "__main__":
    run_checker()
