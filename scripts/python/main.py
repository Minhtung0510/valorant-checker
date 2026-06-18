"""
main.py — Valorant Account Checker với GoLogin Integration.

YÊU CẦU:
    1. GoLogin App đã cài đặt: https://gologin.com
    2. Tạo GoLogin profiles thủ công trong app
    3. Mỗi profile = 1 account Valorant (đã đăng nhập Riot)

CÁCH SỬ DỤNG:
    1. pip install -r requirements.txt
    2. python -m playwright install chromium
    3. Tạo GoLogin profiles trong app (mỗi account 1 profile)
    4. Điền thông tin vào accounts.txt
    5. python main.py

FORMAT accounts.txt:
    username:password:region:proxy:profile_id:ws_url
    
    Ví dụ:
    acc1@gmail.com:pass123:ap:http://user:pass@proxy:8080:abc123:
    acc2@gmail.com:pass456:eu::def456:ws://localhost:9222
    
    - profile_id: ID từ GoLogin app (Settings > Profile ID)
    - ws_url: WebSocket URL (để trống = tự động tìm)
"""
from __future__ import annotations

import asyncio
import subprocess as _subprocess
import json
import logging
import os
import random
import re
import secrets
import shutil
import sys
import threading
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import httpx
import psutil
from nopecha_solver import NopechaSolver

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Setup logging
LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("valorant_checker")
logger.setLevel(logging.INFO)

ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", "%H:%M:%S"))
logger.addHandler(ch)

fh = logging.FileHandler(LOG_DIR / f"run_{datetime.now():%Y%m%d_%H%M%S}.log", encoding="utf-8")
fh.setLevel(logging.DEBUG)
fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
logger.addHandler(fh)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR = Path(__file__).parent
if load_dotenv:
    load_dotenv(SCRIPT_DIR / ".env")

ACCOUNTS_FILE = SCRIPT_DIR / "accounts.txt"
PROFILES_CACHE = SCRIPT_DIR / "profiles_cache.json"
PROFILES_DIR = SCRIPT_DIR / "profiles"
PROXIES_FILE = SCRIPT_DIR / "proxies.txt"
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", r"C:\Users\WORK\Desktop\Check-done"))

# GoLogin / Orbita browser path
GOLOGIN_BROWSER_PATH = Path(os.getenv(
    "GOLOGIN_BROWSER",
    r"C:\Users\WORK\Downloads\Gologin\All-Browsers\orbita-browser-145\chrome.exe",
))

CONCURRENCY = int(os.getenv("CONCURRENCY", "2"))  # Số browser chạy song song

# Port counter cho mỗi browser instance
_next_debug_port = 9222

# Riot constants
RIOT_PLATFORM = (
    "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVm"
    "Vyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9"
)
UUID_SKINS = "e7c63390-eda7-46e0-bb7a-a6abdacd2433"

RANK_NAMES = [
    "Unrated", "Unrated", "Unrated",
    "Iron 1","Iron 2","Iron 3",
    "Bronze 1","Bronze 2","Bronze 3",
    "Silver 1","Silver 2","Silver 3",
    "Gold 1","Gold 2","Gold 3",
    "Platinum 1","Platinum 2","Platinum 3",
    "Diamond 1","Diamond 2","Diamond 3",
    "Ascendant 1","Ascendant 2","Ascendant 3",
    "Immortal 1","Immortal 2","Immortal 3",
    "Radiant",
]

# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Account:
    username: str
    password: str
    region: str = "ap"
    proxy: str = ""
    profile_id: str = ""
    ws_url: str = ""
    
    @staticmethod
    def parse(line: str) -> Optional["Account"]:
        """Parse 1 dòng từ accounts.txt"""
        line = line.strip()
        if not line or line.startswith("#"):
            return None
        
        # format: username:password:region:proxy:profile_id:ws_url
        parts = line.split(":")
        if len(parts) < 2:
            return None
        
        return Account(
            username=parts[0],
            password=parts[1],
            region=parts[2].lower() if len(parts) > 2 else "ap",
            proxy=parts[3] if len(parts) > 3 else "",
            profile_id=parts[4] if len(parts) > 4 else "",
            ws_url=parts[5] if len(parts) > 5 else "",
        )


@dataclass
class ProxyInfo:
    """Thông tin proxy đã parse từ proxies.txt.
    
    Format mỗi dòng: ip:port:user:pass hoặc ip:port
    """
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
        """URL đầy đủ cho httpx client."""
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


@dataclass
class Result:
    ok: bool
    username: str
    password: str = ""
    game_name: str = ""
    tag_line: str = ""
    puuid: str = ""
    region: str = ""
    level: int = 0
    tier: int = 0
    rr: int = 0
    vp: int = 0
    rp: int = 0
    kc: int = 0
    skins_count: int = 0
    skin_names: list[str] = field(default_factory=list)
    skin_details: list[dict[str, str]] = field(default_factory=list)
    status: str = "error"
    status_label: str = "❌ ERROR"
    error: str = ""
    country: str = ""
    email_verified: bool = False
    phone_verified: bool = False
    created_at: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CheckerRunSummary:
    results: list[Result]
    report_path: Optional[Path]
    cancelled: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# GOLOGIN CONNECTION
# ═══════════════════════════════════════════════════════════════════════════════

def _alloc_debug_port() -> int:
    """Cấp 1 debug port duy nhất cho mỗi browser instance."""
    global _next_debug_port
    port = _next_debug_port
    _next_debug_port += 1
    return port


class GoLoginBrowser:
    """
    Tự động launch GoLogin Orbita browser rồi kết nối qua CDP.
    
    Flow:
    1. Launch chrome.exe (Orbita) với --remote-debugging-port
    2. Đợi browser sẵn sàng
    3. Kết nối Playwright qua CDP
    """
    
    def __init__(
        self,
        account: Account,
        proxy_info: Optional[ProxyInfo] = None,
        browser_path: Optional[Path] = None,
        profiles_dir: Optional[Path] = None,
        extension_path: Optional[Path] = None,
    ):
        self.account = account
        self.browser = None
        self.context = None
        self.page = None
        self._process: _subprocess.Popen | None = None
        self._port: int = 0
        self._playwright = None
        self._pw_context_manager = None
        self._proxy: Optional[ProxyInfo] = proxy_info
        self._cdp_session = None
        self._gologin = None
        self._profile_dir: Optional[Path] = None
        self._browser_path = browser_path or GOLOGIN_BROWSER_PATH
        self._profiles_dir = profiles_dir or PROFILES_DIR
        self._extension_path = Path(extension_path).resolve() if extension_path else None
        self.login_failure: Optional[tuple[str, str, str]] = None

    def _extension_args(self) -> list[str]:
        if not self._extension_path:
            return ["--disable-extensions"]

        extension_dir = str(self._extension_path)
        return [
            f"--disable-extensions-except={extension_dir}",
            f"--load-extension={extension_dir}",
        ]
    
    async def connect(self) -> bool:
        """
        Launch Orbita browser rồi kết nối vào.
        Returns True nếu thành công.
        """
        # Nếu có ws_url sẵn thì connect trực tiếp (không cần launch)
        if self.account.ws_url:
            if self._extension_path:
                logger.warning("  Extension path is ignored when connecting to an existing ws_url browser")
            return await self._connect_ws(self.account.ws_url)

        if self.account.profile_id and os.getenv("GOLOGIN_TOKEN", "").strip():
            connected = await self._start_gologin_profile()
            if connected:
                return True
            logger.warning(f"  GoLogin profile start failed for {self.account.username}; falling back to direct Orbita launch")

        # Configure authenticated proxies before Chromium creates its first
        # HTTPS tunnel. Supplying credentials later through CDP is unreliable.
        if self._proxy and self._proxy.username:
            return await self._launch_persistent_with_proxy()
        
        # Tự launch Orbita browser
        return await self._launch_and_connect()

    async def _start_gologin_profile(self) -> bool:
        """Start an existing GoLogin profile through the official SDK."""
        try:
            from gologin import GoLogin
        except ImportError:
            logger.error("  GoLogin SDK is not installed. Run: pip install gologin")
            return False

        if self._proxy:
            logger.info("  Using proxy configured inside GoLogin profile; proxies.txt is ignored for SDK-started profiles")
        if self._extension_path:
            logger.info("  Extension path is ignored for SDK-started GoLogin profiles; install it inside the GoLogin profile")

        options = {
            "token": os.getenv("GOLOGIN_TOKEN", "").strip(),
            "profile_id": self.account.profile_id,
            "executablePath": str(self._browser_path),
        }
        try:
            logger.info(f"  Starting GoLogin profile {self.account.profile_id} for {self.account.username}")
            self._gologin = GoLogin(options)
            debugger_address = await asyncio.to_thread(self._gologin.start)
            if not debugger_address:
                logger.error("  GoLogin SDK returned no debugger address")
                return False

            cdp_url = str(debugger_address)
            if not cdp_url.startswith(("http://", "https://", "ws://", "wss://")):
                cdp_url = f"http://{cdp_url}"
            logger.info(f"  GoLogin profile ready: {cdp_url}")
            return await self._connect_ws(cdp_url)
        except Exception as exc:
            logger.error(f"  GoLogin profile start error: {exc}")
            try:
                if self._gologin:
                    await asyncio.to_thread(self._gologin.stop)
            except Exception:
                pass
            self._gologin = None
            return False

    async def _launch_persistent_with_proxy(self) -> bool:
        chrome_exe = self._browser_path
        if not chrome_exe.exists():
            logger.error(f"  GoLogin browser not found: {chrome_exe}")
            return False

        safe_name = re.sub(r'[^\w.-]', '_', self.account.username)
        self._profile_dir = self._profiles_dir / f"{safe_name}_{hash(self.account.username) & 0xFFFFFFFF}"
        self._profile_dir.mkdir(parents=True, exist_ok=True)

        proxy = self._proxy
        logger.info(f"  Launching Orbita for {self.account.username} via authenticated proxy {proxy.server}")
        try:
            from playwright.async_api import async_playwright

            self._pw_context_manager = async_playwright()
            self._playwright = await self._pw_context_manager.__aenter__()
            self.context = await self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self._profile_dir),
                executable_path=str(chrome_exe),
                headless=False,
                proxy={
                    "server": f"http://{proxy.server}",
                    "username": proxy.username,
                    "password": proxy.password,
                },
                args=[
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-background-networking",
                    "--disable-sync",
                    "--disable-translate",
                    "--metrics-recording-only",
                    "--no-service-autorun",
                    "--password-store=basic",
                    *self._extension_args(),
                ],
            )
            if self.context.pages:
                self.page = self.context.pages[0]
            else:
                self.page = await self.context.new_page()
            logger.info(f"  Browser ready via authenticated proxy {proxy.server}")
            return True
        except Exception as exc:
            logger.error(f"  Authenticated proxy browser launch failed: {exc}")
            return False
    
    async def _launch_and_connect(self) -> bool:
        """Launch Orbita browser rồi kết nối qua CDP."""
        chrome_exe = self._browser_path
        if not chrome_exe.exists():
            logger.error(f"  GoLogin browser not found: {chrome_exe}")
            return False
        
        # Tạo user-data-dir riêng cho mỗi account
        safe_name = re.sub(r'[^\w.-]', '_', self.account.username)
        self._profile_dir = self._profiles_dir / f"{safe_name}_{hash(self.account.username) & 0xFFFFFFFF}"
        self._profile_dir.mkdir(parents=True, exist_ok=True)
        
        self._port = _alloc_debug_port()
        
        # Build command
        cmd = [
            str(chrome_exe),
            f"--remote-debugging-port={self._port}",
            f"--user-data-dir={self._profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-translate",
            "--metrics-recording-only",
            "--no-service-autorun",
            "--password-store=basic",
            *self._extension_args(),
            "about:blank",
        ]
        
        # Thêm proxy server flag nếu có proxy
        if self._proxy:
            cmd.insert(-1, f"--proxy-server={self._proxy.server}")
        
        proxy_log = f" via proxy {self._proxy.server}" if self._proxy else ""
        extension_log = f" with extension {self._extension_path}" if self._extension_path else ""
        logger.info(f"  Launching Orbita on port {self._port} for {self.account.username}{proxy_log}{extension_log}")
        
        try:
            self._process = _subprocess.Popen(
                cmd,
                stdout=_subprocess.DEVNULL,
                stderr=_subprocess.DEVNULL,
                creationflags=_subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
            )
        except Exception as e:
            logger.error(f"  Failed to launch browser: {e}")
            return False
        
        # Đợi browser ready (poll /json/version)
        cdp_url = f"http://localhost:{self._port}"
        ready = False
        for attempt in range(30):  # Max 15 giây
            await asyncio.sleep(0.5)
            try:
                async with httpx.AsyncClient(timeout=2.0) as client:
                    resp = await client.get(f"{cdp_url}/json/version")
                    if resp.is_success:
                        data = resp.json()
                        ws_url = data.get("webSocketDebuggerUrl", "")
                        if ws_url:
                            logger.info(f"  Browser ready on port {self._port}")
                            ready = True
                            break
            except:
                pass
        
        if not ready:
            logger.error(f"  Browser failed to start on port {self._port}")
            self._kill_process()
            return False
        
        # Kết nối Playwright qua CDP
        return await self._connect_ws(f"http://localhost:{self._port}")
    
    async def _connect_ws(self, ws_url: str) -> bool:
        """Kết nối qua WebSocket/CDP URL."""
        try:
            from playwright.async_api import async_playwright
            
            self._pw_context_manager = async_playwright()
            self._playwright = await self._pw_context_manager.__aenter__()
            self.browser = await self._playwright.chromium.connect_over_cdp(ws_url)
            await self._setup_context()
            return True
        except Exception as e:
            logger.error(f"  CDP connect error: {e}")
            return False
    
    async def _setup_context(self):
        """Setup browser context và page."""
        if not self.browser:
            return

        if self.browser.contexts:
            self.context = self.browser.contexts[0]
        else:
            self.context = await self.browser.new_context()

        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = await self.context.new_page()

        # Setup proxy authentication nếu có proxy với credentials
        if self._proxy and self._proxy.username:
            await self._setup_proxy_auth()

        # Inject NopeCHA API key vào extension
        await self._inject_nopecha_key()

    async def _inject_nopecha_key(self):
        """Inject NopeCHA API key vào extension qua Magic URL method.

        Navigate đến https://nopecha.com/setup#{key} - extension sẽ tự động
        đọc key từ URL hash và lưu vào settings.
        """
        nopecha_key = os.getenv("NOPECHA_API_KEY", "").strip()
        if not nopecha_key or not self.page:
            if not nopecha_key:
                # Try to read API key from the answer file as fallback
                try:
                    from pathlib import Path
                    answer_path = Path(r"C:\Users\WORK\valorant-checker\scripts\câu trả lời.txt")
                    if answer_path.is_file():
                        for line in answer_path.read_text(encoding="utf-8").splitlines():
                            if "API Key" in line:
                                # Expected format: API Key : <key>
                                parts = line.split(":", 1)
                                if len(parts) == 2:
                                    extracted = parts[1].strip()
                                    if extracted:
                                        nopecha_key = extracted
                                        logger.debug("  Loaded NOPECHA_API_KEY from answer file")
                                        break
                except Exception as e:
                    logger.debug(f"  Failed to load API key from answer file: {e}")
                if not nopecha_key:
                    logger.debug("  NOPECHA_API_KEY not set, skipping NopeCHA injection")
            return

        try:
            await self.page.goto(f"https://nopecha.com/setup#{nopecha_key}", timeout=10000)
            await asyncio.sleep(2)
            logger.info(f"  NopeCHA key injected via Magic URL for {self.account.username}")
        except Exception as e:
            logger.warning(f"  NopeCHA Magic URL injection error: {e}")

    async def _setup_proxy_auth(self):
        """Tự động xác thực proxy qua CDP Fetch domain.
        
        Khi browser được launch với --proxy-server=host:port, proxy yêu cầu
        xác thực sẽ trả về 407. CDP Fetch domain bắt sự kiện authRequired
        và tự động điền credentials mà không cần mở dialog.
        """
        if not self.page or not self._proxy:
            return
        try:
            self._cdp_session = await self.context.new_cdp_session(self.page)
            await self._cdp_session.send("Fetch.enable", {"handleAuthRequests": True})
            
            proxy = self._proxy
            cdp = self._cdp_session

            def schedule_cdp(method: str, payload: dict) -> None:
                task = asyncio.create_task(cdp.send(method, payload))

                def log_failure(done_task: asyncio.Task) -> None:
                    try:
                        done_task.result()
                    except Exception as exc:
                        logger.debug(f"  Proxy CDP handler {method} failed: {exc}")

                task.add_done_callback(log_failure)

            def on_request_paused(params):
                schedule_cdp("Fetch.continueRequest", {"requestId": params["requestId"]})
            
            def on_auth_required(params):
                challenge = params.get("authChallenge", {})
                if challenge.get("source") == "Proxy":
                    response = {
                        "response": "ProvideCredentials",
                        "username": proxy.username,
                        "password": proxy.password,
                    }
                else:
                    response = {"response": "Default"}
                schedule_cdp(
                    "Fetch.continueWithAuth",
                    {"requestId": params["requestId"], "authChallengeResponse": response},
                )
            
            self._cdp_session.on("Fetch.requestPaused", on_request_paused)
            self._cdp_session.on("Fetch.authRequired", on_auth_required)
            logger.info(f"  Proxy auth handler ready for {self._proxy.server}")
        except Exception as e:
            logger.warning(f"  Proxy auth setup failed: {e}")
    
    def _kill_process(self):
        """Kill browser process."""
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except:
                try:
                    self._process.kill()
                except:
                    pass
            self._process = None

    def _kill_process_tree(self):
        """Force-kill the browser process tree when graceful shutdown hangs."""
        target_pids: set[int] = set()
        if self._process:
            target_pids.add(self._process.pid)

        profile_arg = str(self._profile_dir).lower() if self._profile_dir else ""
        port_arg = f"--remote-debugging-port={self._port}" if self._port else ""
        for process in psutil.process_iter(["pid", "cmdline"]):
            try:
                command_line = " ".join(process.info.get("cmdline") or []).lower()
                if (profile_arg and profile_arg in command_line) or (port_arg and port_arg in command_line):
                    target_pids.add(process.info["pid"])
            except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                continue

        for pid in sorted(target_pids, reverse=True):
            try:
                process = psutil.Process(pid)
                children = process.children(recursive=True)
                for child in reversed(children):
                    try:
                        child.kill()
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        pass
                process.kill()
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass

        if target_pids:
            remaining = []
            for pid in target_pids:
                try:
                    remaining.append(psutil.Process(pid))
                except psutil.NoSuchProcess:
                    pass
            _, alive = psutil.wait_procs(remaining, timeout=3)
            for process in alive:
                try:
                    process.kill()
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
        self._process = None

    async def _delete_temporary_profile(self):
        """Xóa profile do script tự tạo sau khi browser đã đóng."""
        profile_dir = self._profile_dir
        self._profile_dir = None
        if not profile_dir or not profile_dir.exists():
            return

        for attempt in range(5):
            try:
                await asyncio.to_thread(shutil.rmtree, profile_dir)
                logger.info(f"  Deleted temporary profile: {profile_dir}")
                return
            except OSError as e:
                if attempt == 4:
                    logger.warning(f"  Cannot delete temporary profile {profile_dir}: {e}")
                    return
                await asyncio.sleep(0.5 * (attempt + 1))
    
    async def disconnect(self):
        """Ngắt kết nối và kill browser."""
        async def close_gracefully():
            try:
                if self._cdp_session:
                    await self._cdp_session.detach()
            except Exception:
                pass
            try:
                if self.browser and not self._process:
                    await self.browser.close()
            except Exception:
                pass
            try:
                if self.context and not self.browser:
                    await self.context.close()
            except Exception:
                pass
            try:
                if self._pw_context_manager:
                    await self._pw_context_manager.__aexit__(None, None, None)
            except Exception:
                pass

        try:
            await asyncio.wait_for(close_gracefully(), timeout=4)
        except asyncio.TimeoutError:
            logger.warning(f"  Browser close timed out for {self.account.username}; killing process tree")
        finally:
            if self._gologin:
                try:
                    await asyncio.to_thread(self._gologin.stop)
                    logger.info(f"  Stopped GoLogin profile for {self.account.username}")
                except Exception as exc:
                    logger.warning(f"  GoLogin profile stop failed for {self.account.username}: {exc}")
                self._gologin = None
            await asyncio.to_thread(self._kill_process_tree)
        await self._delete_temporary_profile()
    
    async def is_logged_in(self) -> bool:
        """Kiểm tra đã đăng nhập Riot chưa."""
        if not self.context:
            return False
        
        try:
            # Thử gọi userinfo
            cookies = await self.context.cookies()
            cookie_dict = {c["name"]: c["value"] for c in cookies if c.get("name")}
            
            if "ssid" in cookie_dict or "clid" in cookie_dict:
                # Có session cookie - thử verify
                version = await self._get_version()
                headers = {
                    "Authorization": f"Bearer test",
                    "X-Riot-ClientVersion": version,
                    "X-Riot-ClientPlatform": RIOT_PLATFORM,
                }
                
                # Thử get userinfo
                async with httpx.AsyncClient(timeout=10.0) as client:
                    r = await client.get(
                        "https://auth.riotgames.com/userinfo",
                        headers=headers,
                        cookies=cookie_dict,
                    )
                    return r.status_code == 401  # 401 = có cookie nhưng hết hạn, có thể login lại
            
            return False
        except:
            return False
    
    async def get_tokens(self) -> Optional[dict]:
        """
        Lấy tokens từ GoLogin browser.
        Ưu tiên: cookies -> lockfile -> browser login
        """
        if not self.context:
            return None
        
        # Thử lấy từ cookies
        tokens = await self._get_from_cookies()
        if tokens:
            return tokens
        
        # Thử lockfile (nếu Valorant đang chạy)
        tokens = await self._get_from_lockfile()
        if tokens:
            return tokens
        
        return None
    
    async def _get_from_cookies(self) -> Optional[dict]:
        """Lấy tokens bằng cách exchange cookies."""
        if not self.context:
            return None
        
        try:
            cookies = await self.context.cookies()
            cookie_dict = {c["name"]: c["value"] for c in cookies if c.get("name")}
            
            if not cookie_dict:
                return None
            
            version = await self._get_version()
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": f"RiotClient/80.0.1.1024.4762 rso-auth (Windows;10;;Professional, x64)",
                "X-Riot-ClientVersion": version,
                "X-Riot-ClientPlatform": RIOT_PLATFORM,
            }
            
            # Proxy
            proxies = {}
            if self.account.proxy:
                proxies = {"http://": self.account.proxy, "https://": self.account.proxy}
            
            async with httpx.AsyncClient(timeout=30.0, proxies=proxies) as client:
                # Exchange cookies
                r = await client.post(
                    "https://authenticate.riotgames.com/api/v1/login",
                    headers=headers,
                    json={
                        "clientId": "riot-client",
                        "language": "en_US",
                        "platform": "windows",
                        "remember": False,
                        "riot_identity": {"language": "en_US", "state": "auth"},
                        "sdkVersion": "release-5.0.0.358.4781",
                        "type": "auth",
                    },
                    cookies=cookie_dict,
                )
                
                if not r.is_success:
                    return None
                
                data = r.json()

                # Check captcha
                if data.get("captcha"):
                    logger.warning("  Captcha required")
                    return None

                # Get session_token
                session_token = data.get("session_token") or data.get("success", {}).get("session_token")
                
                if not session_token:
                    # Thử kiểm tra xem cookies có valid không
                    # Nếu response có login_token thì cookies còn valid
                    login_token = data.get("login_token") or data.get("success", {}).get("login_token")
                    if login_token:
                        return await self._exchange_login_token(login_token, cookie_dict)
                    return None
                
                # Get access token
                r2 = await client.post(
                    "https://auth.riotgames.com/api/v1/authorization",
                    headers=headers,
                    json={
                        "client_id": "riot-client",
                        "nonce": secrets.token_urlsafe(16),
                        "redirect_uri": "http://localhost/redirect",
                        "response_type": "token id_token",
                        "scope": "openid link ban lol_region account",
                    },
                    cookies=cookie_dict,
                )
                
                if not r2.is_success:
                    return None
                
                uri = r2.json().get("response", {}).get("parameters", {}).get("uri", "")
                if not uri:
                    return None
                
                # Parse token
                fragment = uri.split("#", 1)[-1]
                params = {}
                for pair in fragment.split("&"):
                    if "=" in pair:
                        k, _, v = pair.partition("=")
                        params[k] = v
                
                access_token = params.get("access_token", "")
                if not access_token:
                    return None
                
                # Get entitlements
                ent_resp = await client.post(
                    "https://entitlements.auth.riotgames.com/api/token/v1",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={},
                )
                entitlements = ""
                if ent_resp.is_success:
                    entitlements = ent_resp.json().get("entitlements_token", "")
                
                # Get user info
                user_resp = await client.get(
                    "https://auth.riotgames.com/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                puuid = ""
                if user_resp.is_success:
                    puuid = user_resp.json().get("sub", "")
                
                logger.info(f"  Got tokens via cookies for {self.account.username}")
                return {
                    "access_token": access_token,
                    "entitlements_token": entitlements,
                    "puuid": puuid,
                }
                
        except Exception as e:
            logger.error(f"  Cookie exchange error: {e}")
            return None
    
    async def _exchange_login_token(self, login_token: str, cookies: dict) -> Optional[dict]:
        """Exchange login_token sang tokens."""
        try:
            version = await self._get_version()
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": f"RiotClient/80.0.1.1024.4762 rso-auth (Windows;10;;Professional, x64)",
                "X-Riot-ClientVersion": version,
                "X-Riot-ClientPlatform": RIOT_PLATFORM,
            }
            
            proxies = {}
            if self.account.proxy:
                proxies = {"http://": self.account.proxy, "https://": self.account.proxy}
            
            async with httpx.AsyncClient(timeout=30.0, proxies=proxies) as client:
                # Exchange login_token
                r = await client.post(
                    "https://auth.riotgames.com/api/v1/login-token",
                    headers=headers,
                    json={
                        "authentication_type": "RiotAuth",
                        "code_verifier": "",
                        "login_token": login_token,
                        "persist_login": False,
                    },
                    cookies=cookies,
                )
                
                if not r.is_success:
                    return None
                
                # Get access token
                r2 = await client.post(
                    "https://auth.riotgames.com/api/v1/authorization",
                    headers=headers,
                    json={
                        "client_id": "riot-client",
                        "nonce": secrets.token_urlsafe(16),
                        "redirect_uri": "http://localhost/redirect",
                        "response_type": "token id_token",
                        "scope": "openid link ban lol_region account",
                    },
                    cookies=cookies,
                )
                
                if not r2.is_success:
                    return None
                
                uri = r2.json().get("response", {}).get("parameters", {}).get("uri", "")
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
                
                # Get entitlements
                ent_resp = await client.post(
                    "https://entitlements.auth.riotgames.com/api/token/v1",
                    headers={"Authorization": f"Bearer {access_token}"},
                    json={},
                )
                entitlements = ""
                if ent_resp.is_success:
                    entitlements = ent_resp.json().get("entitlements_token", "")
                
                # Get user info
                user_resp = await client.get(
                    "https://auth.riotgames.com/userinfo",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                puuid = ""
                if user_resp.is_success:
                    puuid = user_resp.json().get("sub", "")
                
                return {
                    "access_token": access_token,
                    "entitlements_token": entitlements,
                    "puuid": puuid,
                }
                
        except Exception as e:
            logger.error(f"  Login token exchange error: {e}")
            return None
    
    async def _get_from_lockfile(self) -> Optional[dict]:
        """Lấy tokens từ Valorant/Riot Client lockfile."""
        import base64
        import subprocess
        
        lockfile_path = Path(os.getenv("LOCALAPPDATA", 
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
            auth = base64.b64encode(f"riot:{password}".encode()).decode()
            
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
            
            if at and et:
                logger.info("  Got tokens from lockfile")
                return {
                    "access_token": at,
                    "entitlements_token": et,
                    "puuid": puuid,
                }
        except:
            pass
        
        return None

    async def _find_hcaptcha_sitekey(self) -> Optional[str]:
        if not self.page:
            return None

        try:
            return await self.page.evaluate(
                """() => {
                    const selectors = [
                        "[data-sitekey]",
                        "iframe[src*='hcaptcha.com'][src*='sitekey=']",
                        "iframe[src*='newassets.hcaptcha.com'][src*='sitekey=']"
                    ];

                    for (const selector of selectors) {
                        for (const el of document.querySelectorAll(selector)) {
                            const direct = el.getAttribute("data-sitekey");
                            if (direct) return direct;

                            const src = el.getAttribute("src");
                            if (src) {
                                try {
                                    const parsed = new URL(src, window.location.href);
                                    const sitekey = parsed.searchParams.get("sitekey");
                                    if (sitekey) return sitekey;
                                } catch (_) {}
                            }
                        }
                    }

                    const html = document.documentElement.innerHTML;
                    const match = html.match(/sitekey["'\\s:=]+([0-9a-fA-F-]{20,})/);
                    return match ? match[1] : null;
                }"""
            )
        except Exception as exc:
            logger.debug(f"  hCaptcha sitekey detection failed: {exc}")
            return None

    async def _find_hcaptcha_rqdata(self) -> str:
        if not self.page:
            return ""

        try:
            return await self.page.evaluate(
                """() => {
                    const sources = [
                        ...Array.from(document.querySelectorAll("iframe[src*='hcaptcha']")).map(el => el.src || ""),
                        document.documentElement.innerHTML
                    ];

                    for (const source of sources) {
                        try {
                            const parsed = new URL(source, window.location.href);
                            const rqdata = parsed.searchParams.get("rqdata");
                            if (rqdata) return rqdata;
                        } catch (_) {}

                        const match = source.match(/["']rqdata["']\\s*:\\s*["']([^"']+)["']/);
                        if (match) return match[1];
                    }
                    return "";
                }"""
            ) or ""
        except Exception as exc:
            logger.debug(f"  hCaptcha rqdata detection failed: {exc}")
            return ""

    async def _browser_user_agent(self) -> str:
        if not self.page:
            return ""

        try:
            return await self.page.evaluate("() => navigator.userAgent") or ""
        except Exception:
            return ""

    def _nopecha_proxy_payload(self) -> Optional[dict]:
        proxy = self._proxy
        if not proxy:
            return None

        payload = {
            "scheme": "http",
            "host": proxy.host,
            "port": str(proxy.port),
        }
        if proxy.username:
            payload["username"] = proxy.username
            payload["password"] = proxy.password
        return payload

    async def _inject_hcaptcha_token(self, token: str) -> bool:
        if not self.page:
            return False

        try:
            return await self.page.evaluate(
                """(token) => {
                    const responseNames = ["h-captcha-response", "g-recaptcha-response"];

                    for (const name of responseNames) {
                        let fields = Array.from(document.querySelectorAll(`[name="${name}"]`));
                        if (!fields.length) {
                            const textarea = document.createElement("textarea");
                            textarea.name = name;
                            textarea.style.display = "none";
                            document.body.appendChild(textarea);
                            fields = [textarea];
                        }

                        for (const field of fields) {
                            field.value = token;
                            field.innerHTML = token;
                            field.dispatchEvent(new Event("input", { bubbles: true }));
                            field.dispatchEvent(new Event("change", { bubbles: true }));
                        }
                    }

                    let callbackCalled = false;
                    const cfg = window.___grecaptcha_cfg;
                    if (cfg && cfg.clients) {
                        const visit = (obj, seen = new Set()) => {
                            if (!obj || typeof obj !== "object" || seen.has(obj)) return;
                            seen.add(obj);
                            for (const [key, value] of Object.entries(obj)) {
                                if (typeof value === "function" && key.toLowerCase().includes("callback")) {
                                    try {
                                        value(token);
                                        callbackCalled = true;
                                    } catch (_) {}
                                } else if (value && typeof value === "object") {
                                    visit(value, seen);
                                }
                            }
                        };
                        visit(cfg.clients);
                    }

                    window.dispatchEvent(new Event("captcha-solved"));
                    return true;
                }""",
                token,
            )
        except Exception as exc:
            logger.warning(f"  Failed to inject hCaptcha token: {exc}")
            return False

    async def _solve_hcaptcha_if_present(self) -> Optional[bool]:
        """
        Phát hiện hCaptcha và để extension NopeCHA tự động giải.
        Extension sẽ tự động inject solution vào page.
        """
        if not self.page:
            return None

        sitekey = await self._find_hcaptcha_sitekey()
        if not sitekey:
            return None

        api_key = os.getenv("NOPECHA_API_KEY", "").strip()
        if not api_key:
            logger.warning("  hCaptcha detected but NOPECHA_API_KEY is not configured")
            return False

        logger.info(f"  hCaptcha detected (sitekey: {sitekey[:20]}...) - waiting for NopeCHA extension to solve...")

        # Đợi extension NopeCHA tự động giải captcha
        # Extension sẽ tự động detect hCaptcha iframe và submit solution
        max_wait = 120  # 2 phút
        check_interval = 2  # Check mỗi 2 giây

        for attempt in range(max_wait // check_interval):
            await asyncio.sleep(check_interval)

            # Check xem captcha đã biến mất chưa (dấu hiệu đã được giải)
            captcha_gone = await self.page.evaluate(
                """() => {
                    // Check nếu hCaptcha iframe không còn hoặc đã hidden
                    const hcaptchaIframes = document.querySelectorAll('iframe[src*="hcaptcha"]');
                    if (hcaptchaIframes.length === 0) return true;

                    // Check nếu có response token
                    const responseField = document.querySelector('[name="h-captcha-response"]');
                    if (responseField && responseField.value && responseField.value.length > 50) {
                        return true;
                    }

                    // Check nếu captcha container đã hidden
                    for (const iframe of hcaptchaIframes) {
                        const container = iframe.closest('[class*="captcha"], [id*="captcha"]');
                        if (container) {
                            const style = window.getComputedStyle(container);
                            if (style.display === 'none' || style.visibility === 'hidden') {
                                return true;
                            }
                        }
                    }

                    return false;
                }"""
            )

            if captcha_gone:
                logger.info(f"  NopeCHA extension solved hCaptcha for {self.account.username} (after {attempt * check_interval}s)")

                # Click submit button nếu có
                try:
                    submit_btn = await self.page.query_selector('button[data-testid="btn-signin-submit"]')
                    if submit_btn and await submit_btn.is_visible():
                        await submit_btn.click()
                        logger.info(f"  Clicked submit button for {self.account.username}")
                except Exception as e:
                    logger.debug(f"  Submit button click error: {e}")

                return True

            # Log tiến độ mỗi 10 giây
            if attempt % 5 == 0 and attempt > 0:
                logger.debug(f"  Still waiting for NopeCHA extension... ({attempt * check_interval}s)")

        logger.warning(f"  NopeCHA extension did not solve hCaptcha within {max_wait}s for {self.account.username}")
        return False
    
    async def do_login(self) -> Optional[dict]:
        """Đăng nhập trực tiếp trên browser."""
        if not self.page:
            return None
        
        try:
            # Intercept localhost redirect to prevent loading failure and chrome-error
            async def handle_redirect(route):
                await route.fulfill(
                    status=200,
                    content_type="text/html",
                    body="<html><body><h1>Login successful! Processing tokens...</h1></body></html>"
                )
            # Chỉ intercept khi URL thực sự chuyển hướng về localhost/redirect
            await self.page.route(lambda url: url.startswith("http://localhost/redirect"), handle_redirect)

            # Navigate to Riot auth
            await self.page.goto(
                "https://auth.riotgames.com/authorize"
                "?redirect_uri=http://localhost/redirect"
                "&client_id=riot-client"
                "&response_type=token%20id_token"
                "&nonce=1"
                "&scope=openid%20link%20ban%20lol_region%20account",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            
            username_filled = False
            password_filled = False
            captcha_solved = False
            captcha_attempted = False
            
            logger.info(f"  Waiting for login completion for {self.account.username} (max 180s)...")
            
            # Vòng lặp chờ chuyển hướng (180 giây)
            for attempt in range(360):
                await asyncio.sleep(0.5)
                
                # 1. Kiểm tra nếu đã login thành công và chuyển hướng lấy token
                url = self.page.url
                if "access_token=" in url:
                    return await self._parse_token_from_url(url)

                if not captcha_solved and not captcha_attempted and attempt % 4 == 0:
                    captcha_result = await self._solve_hcaptcha_if_present()
                    if captcha_result is not None:
                        captcha_attempted = True
                        captcha_solved = captcha_result

                # Detect terminal login states early instead of waiting 180 seconds.
                if attempt % 2 == 0:
                    try:
                        page_text = (await self.page.locator("body").inner_text(timeout=1_000)).lower()
                        if (
                            "verification required" in page_text
                            and "enter the code" in page_text
                            and "emailed" in page_text
                        ):
                            self.login_failure = (
                                "email_verification",
                                "⚠ EMAIL VERIFICATION",
                                "Riot requires a verification code sent by email",
                            )
                            logger.warning(f"  Email verification required for {self.account.username}")
                            return None

                        credential_message = (
                            "your username or password may be incorrect"
                            in page_text
                        )
                        legacy_message = (
                            "you may need to update to a riot account"
                            in page_text
                        )
                        if credential_message or legacy_message:
                            self.login_failure = (
                                "wrong_credentials_or_legacy",
                                "❌ WRONG LOGIN / LEGACY",
                                "Username/password is incorrect or the account requires a Riot Account update",
                            )
                            logger.warning(f"  Wrong credentials or legacy account: {self.account.username}")
                            return None
                    except Exception:
                        pass

                if not username_filled:
                    try:
                        username_input = await self.page.query_selector('input[name="username"]')
                        if username_input and await username_input.is_visible():
                            val = await username_input.input_value()
                            if not val:
                                await username_input.fill(self.account.username)
                                username_filled = True
                                logger.info(f"  Filled username for {self.account.username}")

                                password_input = await self.page.query_selector('input[name="password"]')
                                if not password_input or not await password_input.is_visible():
                                    await self.page.keyboard.press("Enter")
                                    logger.info("  Pressed Enter on username step")
                    except Exception:
                        pass

                if not password_filled:
                    try:
                        password_input = await self.page.query_selector('input[name="password"]')
                        if password_input and await password_input.is_visible():
                            val = await password_input.input_value()
                            if not val:
                                await password_input.fill(self.account.password)
                                await asyncio.sleep(0.5)
                                # Click nút sign in submit
                                submit_btn = await self.page.query_selector('button[data-testid="btn-signin-submit"]')
                                if submit_btn and await submit_btn.is_visible():
                                    await submit_btn.click()
                                    password_filled = True
                                    logger.info(f"  Filled password and clicked sign in for {self.account.username}")
                    except:
                        pass
            
            logger.warning(f"  Login timeout for {self.account.username}")
            return None
            
        except Exception as e:
            logger.error(f"  Browser login error: {e}")
            return None
    
    async def _parse_token_from_url(self, url: str) -> Optional[dict]:
        """Parse tokens từ redirect URL."""
        try:
            fragment = url.split("#", 1)[-1]
            params = {}
            for pair in fragment.split("&"):
                if "=" in pair:
                    k, _, v = pair.partition("=")
                    params[k] = v
            
            access_token = params.get("access_token", "")
            if not access_token:
                return None
            
            # Get entitlements
            ent_resp = await self.context.request.post(
                "https://entitlements.auth.riotgames.com/api/token/v1",
                headers={"Authorization": f"Bearer {access_token}"},
                data={},
            )
            entitlements = ""
            if ent_resp.ok:
                entitlements = (await ent_resp.json()).get("entitlements_token", "")
            
            # Get user info
            user_resp = await self.context.request.get(
                "https://auth.riotgames.com/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            puuid = ""
            if user_resp.ok:
                puuid = (await user_resp.json()).get("sub", "")
            
            logger.info(f"  Got tokens via browser login for {self.account.username}")
            return {
                "access_token": access_token,
                "entitlements_token": entitlements,
                "puuid": puuid,
            }
        except Exception as e:
            logger.error(f"  Parse token error: {e}")
            return None
    
    async def _get_version(self) -> str:
        """Get Riot client version."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get("https://valorant-api.com/v1/version")
                if resp.is_success:
                    return resp.json()["data"]["riotClientVersion"]
        except:
            pass
        return "release-12.10-shipping-17-4738152"


# Bản đồ ánh xạ level_uuid -> base_skin_name
VALORANT_SKINS_MAP: dict[str, dict[str, str]] = {}

async def load_valorant_skins_map(api_request=None):
    """Tải danh sách skin từ valorant-api.com và ánh xạ các level về skin gốc."""
    global VALORANT_SKINS_MAP
    if VALORANT_SKINS_MAP:
        return
    try:
        if api_request:
            resp = await api_request.get("https://valorant-api.com/v1/weapons/skins", timeout=30_000)
            payload = await resp.json() if resp.ok else {}
        else:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get("https://valorant-api.com/v1/weapons/skins")
                payload = resp.json() if resp.is_success else {}

        for skin in payload.get("data", []):
            base_name = skin.get("displayName", "")
            base_image = skin.get("displayIcon") or ""
            for level in skin.get("levels", []):
                lvl_uuid = level.get("uuid")
                if lvl_uuid:
                    VALORANT_SKINS_MAP[lvl_uuid.lower()] = {
                        "name": base_name,
                        "image": level.get("displayIcon") or base_image,
                    }
        if VALORANT_SKINS_MAP:
            logger.info(f"Loaded {len(VALORANT_SKINS_MAP)} skin levels into map")
        else:
            logger.warning("Valorant skins map response was empty")
    except Exception as e:
        logger.error(f"Failed to load valorant skins map from API: {e}")



# ═══════════════════════════════════════════════════════════════════════════════
# RIOT API
# ═══════════════════════════════════════════════════════════════════════════════

async def get_account_data(
    access_token: str,
    entitlements: str,
    puuid: str,
    region: str,
    proxy: str = "",
    api_request=None,
) -> dict:
    """Lấy tất cả data của account."""
    version = "release-12.10-shipping-17-4738152"
    
    # Get version. Prefer Playwright's request context because it shares the
    # browser networking stack and Windows certificate trust configuration.
    try:
        if api_request:
            resp = await api_request.get("https://valorant-api.com/v1/version", timeout=10_000)
            if resp.ok:
                version = (await resp.json())["data"]["riotClientVersion"]
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get("https://valorant-api.com/v1/version")
                if resp.is_success:
                    version = resp.json()["data"]["riotClientVersion"]
    except Exception as exc:
        logger.warning(f"  Cannot refresh Riot client version: {exc}")
    
    proxies = {}
    if proxy:
        proxies = {"http://": proxy, "https://": proxy}
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Riot-Entitlements-JWT": entitlements,
        "X-Riot-ClientVersion": version,
        "X-Riot-ClientPlatform": RIOT_PLATFORM,
    }
    
    async with httpx.AsyncClient(timeout=15.0, proxies=proxies) as client:
        async def get(url: str, label: str):
            try:
                if api_request:
                    r = await api_request.get(url, headers=headers, timeout=15_000)
                    if r.ok:
                        return await r.json()
                    logger.warning(f"  Riot API {label} returned HTTP {r.status}")
                    return {}

                r = await client.get(url, headers=headers)
                if r.is_success:
                    return r.json()
                logger.warning(f"  Riot API {label} returned HTTP {r.status_code}")
                return {}
            except Exception as exc:
                logger.warning(f"  Riot API {label} failed: {exc}")
                return {}
        
        async def get_mmr(url: str):
            """MMR endpoint - captures ban status from 403/404."""
            try:
                if api_request:
                    r = await api_request.get(url, headers=headers, timeout=15_000)
                    status = r.status
                    if r.ok:
                        return await r.json()
                    body_text = await r.text()
                else:
                    r = await client.get(url, headers=headers)
                    status = r.status_code
                    if r.is_success:
                        return r.json()
                    body_text = r.text

                if status in (403, 404):
                    body_upper = body_text.upper()
                    is_ban = status == 403 and (
                        "BAN" in body_upper or "DENIED" in body_upper or "ACCESS_DENIED" in body_upper
                    )
                    return {"__ban__": is_ban, "__status__": status, "__body__": body_text}
                logger.warning(f"  Riot API mmr returned HTTP {status}")
                return {}
            except Exception as exc:
                logger.warning(f"  Riot API mmr failed: {exc}")
                return {}
        
        # Gọi song song các API cơ bản
        userinfo, wallet, mmr, skins, xp, ranked_restrictions = await asyncio.gather(
            get("https://auth.riotgames.com/userinfo", "userinfo"),
            get(f"https://pd.{region}.a.pvp.net/store/v1/wallet/{puuid}", "wallet"),
            get_mmr(f"https://pd.{region}.a.pvp.net/mmr/v1/players/{puuid}"),
            get(f"https://pd.{region}.a.pvp.net/store/v1/entitlements/{puuid}/{UUID_SKINS}", "skins"),
            get(f"https://pd.{region}.a.pvp.net/account-xp/v1/players/{puuid}", "account-xp"),
            get(
                f"https://pd.{region}.a.pvp.net/restrictions/v1/players/{puuid}/restrictions",
                "competitive-restrictions",
            ),
        )

        if not userinfo:
            raise RuntimeError("Riot userinfo API returned no data")
        if "Entitlements" not in skins:
            raise RuntimeError("Riot inventory API returned no data")
        
        # Parse balances
        bals = wallet.get("Balances", {})
        uuids = list(bals.keys())
        vp = int(bals.get(uuids[0], 0)) if len(uuids) > 0 else 0
        rp = int(bals.get(uuids[1], 0)) if len(uuids) > 1 else 0
        kc = int(bals.get(uuids[2], 0)) if len(uuids) > 2 else 0
        
        # Parse Rank MMR (sử dụng LatestCompetitiveUpdate, nếu không có thì fallback qua competitive history)
        tier, rr = 0, 0
        comp = mmr.get("LatestCompetitiveUpdate", {})
        
        if not comp or not comp.get("MatchID"):
            # Thử lấy lịch sử đấu xếp hạng nếu LatestCompetitiveUpdate trống
            hist = await get(
                f"https://pd.{region}.a.pvp.net/mmr/v1/players/{puuid}/competitivehistory",
                "competitive-history",
            )
            matches = hist.get("Matches", [])
            if matches and isinstance(matches, list) and len(matches) > 0:
                comp = matches[0]
                tier = int(comp.get("TierAfterUpdate", 0))
                rr = int(comp.get("RankedRatingAfterUpdate", 0))
        else:
            tier = int(comp.get("TierAfterUpdate", 0))
            rr = int(comp.get("RankedRatingAfterUpdate", 0))
        
        # Deduplicate skin levels into their base skin and retain display artwork.
        seen_skins: dict[str, dict[str, str]] = {}
        for ent in skins.get("Entitlements", []):
            item_id = ent.get("ItemID", "").lower()
            skin_detail = VALORANT_SKINS_MAP.get(item_id)
            if skin_detail and skin_detail.get("name"):
                seen_skins.setdefault(skin_detail["name"], skin_detail)
        
        skin_details = sorted(seen_skins.values(), key=lambda item: item["name"].casefold())
        skin_names = [item["name"] for item in skin_details]
        skins_count = len(skin_names) if VALORANT_SKINS_MAP else len(skins.get("Entitlements", []))
        
        level = xp.get("Progress", {}).get("Level", xp.get("Level", 0))
        
        # Lấy game_name và tag_line từ object acct
        acct_info = userinfo.get("acct", {})
        game_name = acct_info.get("game_name", "") or userinfo.get("game_name", "")
        tag_line = acct_info.get("tag_line", "") or userinfo.get("tag_line", "")
        
        # Lấy thông tin xác minh & thời gian tạo tài khoản
        email_verified = userinfo.get("email_verified", False)
        phone_verified = userinfo.get("phone_number_verified", False) or userinfo.get("phone_verified", False)
        country = userinfo.get("country", "")
        
        created_at_ms = acct_info.get("created_at")
        created_at_str = ""
        if created_at_ms:
            try:
                from datetime import datetime as dt_class
                created_at_str = dt_class.fromtimestamp(created_at_ms / 1000).strftime("%d/%m/%Y")
            except:
                pass
        
        # ── Determine account ban status ──
        account_status = "active"
        account_status_label = "✅ ACTIVE"
        
        # Priority 1: MMR 403 with BAN keywords
        if mmr.get("__ban__") is True:
            body = mmr.get("__body__", "").upper()
            if "ACCESS_DENIED" in body or "FORBIDDEN" in body:
                account_status = "banned"
                account_status_label = "🔴 BANNED (Access Denied)"
            elif "TEMPORARY" in body:
                account_status = "time_ban"
                account_status_label = "🟡 TIME BAN"
            else:
                account_status = "banned"
                account_status_label = "🔴 BANNED"
        # Priority 2: userinfo.ban.restrictions
        elif isinstance(userinfo.get("ban"), dict):
            ban_info = userinfo["ban"]
            restrictions = ban_info.get("restrictions", [])
            if isinstance(restrictions, list) and len(restrictions) > 0:
                r0 = restrictions[0] if isinstance(restrictions[0], dict) else {}
                reason = r0.get("reason", "") or r0.get("type", "")
                account_status = "banned"
                account_status_label = f"🔴 BANNED: {reason}" if reason else "🔴 BANNED"
            else:
                flag = ban_info.get("flag")
                if flag:
                    rest_until = ban_info.get("rest_until")
                    if rest_until and isinstance(rest_until, (int, float)):
                        account_status = "time_ban"
                        account_status_label = f"🟡 SUSPENDED until {datetime.fromtimestamp(rest_until).strftime('%d/%m/%Y')}"
                    else:
                        account_status = "banned"
                        account_status_label = f"🔴 BANNED: {flag}"
        # Priority 3: userinfo.accountStatus
        elif userinfo.get("accountStatus") and userinfo.get("accountStatus") != "Active":
            account_status = "banned"
            account_status_label = f"🔴 {userinfo['accountStatus']}"
        # Priority 4: AccountFlag
        elif userinfo.get("AccountFlag") and userinfo.get("AccountFlag") != 0:
            account_status = "flagged"
            account_status_label = f"⚠️ FLAGGED: {userinfo['AccountFlag']}"
        # Competitive restrictions are independent of userinfo.ban. Only let them
        # replace ACTIVE so a real account ban always keeps the higher priority.
        # Verification/phone restrictions are kept separate from ordinary queue locks.
        if account_status == "active" and isinstance(ranked_restrictions, dict):
            raw_restrictions = ranked_restrictions.get("restrictions", [])
            if isinstance(raw_restrictions, list) and raw_restrictions:
                restriction_keys = []
                for restriction in raw_restrictions:
                    if not isinstance(restriction, dict):
                        continue
                    key = restriction.get("type") or restriction.get("reason")
                    if key:
                        restriction_keys.append(str(key))

                if restriction_keys:
                    restriction_text = "; ".join(restriction_keys)
                    restriction_upper = restriction_text.upper()
                    if "VERIFY" in restriction_upper or "VERIFICATION" in restriction_upper or "PHONE" in restriction_upper:
                        account_status = "competitive_verify"
                        account_status_label = f"🟠 COMPETITIVE VERIFY: {restriction_text}"
                    else:
                        account_status = "competitive_restricted"
                        account_status_label = f"🟠 COMPETITIVE RESTRICTED: {restriction_text}"
        
        return {
            "game_name": game_name,
            "tag_line": tag_line,
            "puuid": puuid or userinfo.get("sub", ""),
            "level": int(level),
            "vp": vp,
            "rp": rp,
            "kc": kc,
            "tier": tier,
            "rr": rr,
            "skins_count": skins_count,
            "skin_names": skin_names,
            "skin_details": skin_details,
            "region": region,
            "account_status": account_status,
            "account_status_label": account_status_label,
            "country": country,
            "email_verified": email_verified,
            "phone_verified": phone_verified,
            "created_at": created_at_str,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PROCESS ACCOUNT
# ═══════════════════════════════════════════════════════════════════════════════

async def process_account(
    account: Account,
    sem: asyncio.Semaphore,
    proxy_info: Optional[ProxyInfo] = None,
    browser_path: Optional[Path] = None,
    profiles_dir: Optional[Path] = None,
    extension_path: Optional[Path] = None,
) -> Result:
    """Xử lý 1 account."""
    async with sem:
        t0 = time.time()
        
        browser = GoLoginBrowser(
            account,
            proxy_info=proxy_info,
            browser_path=browser_path,
            profiles_dir=profiles_dir,
            extension_path=extension_path,
        )
        
        try:
            # Kết nối GoLogin
            connected = await browser.connect()
            if not connected:
                return Result(
                    ok=False,
                    username=account.username,
                    password=account.password,
                    status="error",
                    status_label="❌ CONNECT FAILED",
                    error="Cannot connect to GoLogin browser",
                )
            
            # Lấy tokens
            tokens = await browser.get_tokens()
            
            # Nếu không có tokens, thử login trên browser
            if not tokens:
                logger.info(f"  No cookies - doing browser login for {account.username}")
                tokens = await browser.do_login()
            
            if not tokens:
                if browser.login_failure:
                    status, status_label, error = browser.login_failure
                    return Result(
                        ok=False,
                        username=account.username,
                        password=account.password,
                        status=status,
                        status_label=status_label,
                        error=error,
                    )
                return Result(
                    ok=False,
                    username=account.username,
                    password=account.password,
                    status="auth_fail",
                    status_label="❌ AUTH FAILED",
                    error="Cannot get tokens",
                )
            
            # Lấy account data
            if not VALORANT_SKINS_MAP and browser.context:
                await load_valorant_skins_map(browser.context.request)

            data = await get_account_data(
                tokens["access_token"],
                tokens["entitlements_token"],
                tokens["puuid"],
                account.region,
                account.proxy,
                api_request=browser.context.request if browser.context else None,
            )
            
            elapsed = time.time() - t0
            logger.info(f"✓ {account.username} ({elapsed:.1f}s) | {data['skins_count']} skins")
            
            return Result(
                ok=True,
                username=account.username,
                password=account.password,
                game_name=data["game_name"],
                tag_line=data["tag_line"],
                puuid=data["puuid"],
                region=data["region"],
                level=data["level"],
                tier=data["tier"],
                rr=data["rr"],
                vp=data["vp"],
                rp=data["rp"],
                kc=data["kc"],
                skins_count=data["skins_count"],
                skin_names=data.get("skin_names", []),
                skin_details=data.get("skin_details", []),
                status=data["account_status"],
                status_label=data["account_status_label"],
                country=data.get("country", ""),
                email_verified=data.get("email_verified", False),
                phone_verified=data.get("phone_verified", False),
                created_at=data.get("created_at", ""),
            )
            
        except Exception as e:
            logger.error(f"Error processing {account.username}: {e}")
            return Result(
                ok=False,
                username=account.username,
                password=account.password,
                status="error",
                status_label="❌ ERROR",
                error=str(e),
            )
        finally:
            try:
                await asyncio.shield(browser.disconnect())
            except asyncio.CancelledError:
                logger.warning(f"  Cleanup was interrupted for {account.username}")
                raise


# ═══════════════════════════════════════════════════════════════════════════════
# OUTPUT
# ═══════════════════════════════════════════════════════════════════════════════

def generate_account_html(r: Result) -> str:
    """Tạo chi tiết tài khoản giống giao diện webapp."""
    is_err = not r.ok or r.status in (
        "banned", "time_ban", "flagged", "competitive_verify",
        "competitive_restricted", "error", "auth_fail",
        "email_verification", "wrong_credentials_or_legacy",
    )
    if is_err:
        cat_label = "Lỗi / Bị Ban"
        cat_color = "#ff5252"
    elif r.skins_count == 0:
        cat_label = "0 Skins"
        cat_color = "#8b978f"
    elif r.skins_count <= 20:
        cat_label = "1-20 Skins"
        cat_color = "#4caf50"
    elif r.skins_count <= 60:
        cat_label = "20-60 Skins"
        cat_color = "#2196f3"
    elif r.skins_count <= 120:
        cat_label = "60-120 Skins"
        cat_color = "#ff9800"
    else:
        cat_label = "120+ Skins"
        cat_color = "#e91e63"

    rank_name = RANK_NAMES[r.tier] if 0 <= r.tier < len(RANK_NAMES) else f"Rank {r.tier}"
    rank_str = f"{rank_name} - {r.rr}RR" if r.tier > 0 else "—"
    is_banned = r.status in ("banned", "time_ban")
    
    import html
    game_name_esc = html.escape(r.game_name)
    tag_line_esc = html.escape(r.tag_line)
    puuid_esc = html.escape(r.puuid)
    region_esc = html.escape(r.region.upper())
    country_esc = html.escape(r.country.upper())
    status_lbl_esc = html.escape(r.status_label)
    
    banned_banner = ""
    if is_banned:
        banned_banner = f'<div style="background:rgba(183,28,28,.2);border:1px solid #b71c1c;border-radius:8px;padding:14px;margin-bottom:16px;color:#ff5252;font-weight:600">⚠ Account bị: {status_lbl_esc}</div>'
    
    email_status = "Yes" if r.email_verified else "No"
    phone_status = "Yes" if r.phone_verified else "No"
    
    status_badge = f"<span class='green-badge'>Active</span>" if r.status == "active" else f"<span class='red-badge'>{status_lbl_esc}</span>"
    skin_details = r.skin_details or [{"name": name, "image": ""} for name in r.skin_names]
    skin_items = "".join(
        f'''<article class="skin-item">
          <div class="skin-art">
            {f'<img src="{html.escape(item.get("image", ""), quote=True)}" alt="{html.escape(item.get("name", ""), quote=True)}" loading="lazy">' if item.get("image") else '<span class="skin-placeholder">No image</span>'}
          </div>
          <div class="skin-name">{html.escape(item.get("name", "Unknown skin"))}</div>
        </article>'''
        for item in skin_details
    )
    skins_section = f"""
  <div class="card skins-card">
    <h3>Skin Collection ({r.skins_count})</h3>
    <div class="skin-grid">{skin_items or '<span class="empty-skins">No mapped skin names found.</span>'}</div>
  </div>"""

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{game_name_esc}#{tag_line_esc} - Valorant Checker</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0f1923;color:#ece8e1;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh}}
header{{background:#1a2634;border-bottom:2px solid #ff4655;padding:16px 24px;display:flex;align-items:center;justify-content:space-between}}
header .brand{{display:flex;align-items:center;gap:12px}}
header .brand .logo{{width:36px;height:36px}}
header .brand .name{{font-size:1.2em;font-weight:700;color:#ff4655;letter-spacing:1px}}
header .right{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
main{{max-width:1100px;margin:0 auto;padding:20px 24px}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}}
.card{{background:#1a2634;border:1px solid #2a3a4a;border-radius:10px;padding:16px}}
.card h3{{color:#ff4655;font-size:.72em;text-transform:uppercase;letter-spacing:.8px;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #2a3a4a}}
.info-row{{display:flex;padding:7px 0;border-bottom:1px solid rgba(42,58,74,.3);font-size:.88em;gap:10px}}
.info-row:last-child{{border-bottom:none}}
.info-row .label{{color:#8b978f;min-width:130px;flex-shrink:0}}
.info-row .val{{font-weight:600;color:#ece8e1;word-break:break-all}}
.info-row .val.small{{font-size:.75em}}
.green-badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.8em;font-weight:600;background:#1b5e20;color:#4caf50}}
.red-badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.8em;font-weight:600;background:#2a1a1a;color:#ff5252}}
.wallet-grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:12px}}
.wallet-card{{background:#0d1520;border:1px solid #2a3a4a;border-radius:8px;padding:10px;text-align:center}}
.wallet-card .val{{font-size:1.1em;font-weight:700;color:#ff4655}}
.wallet-card .lbl{{font-size:.68em;color:#8b978f;text-transform:uppercase;letter-spacing:.5px;margin-top:2px}}
.stat-row{{display:flex;gap:16px;padding-top:8px;border-top:1px solid #2a3a4a}}
.stat-row .s{{font-size:.88em}}
.stat-row .s .n{{font-weight:700;color:#ece8e1}}
.stat-row .s .l{{color:#8b978f;font-size:.8em}}
.cat-badge{{display:inline-block;padding:3px 12px;border-radius:12px;font-size:.8em;font-weight:700;border:1px solid {cat_color};color:{cat_color};background:transparent}}
.cat-badge.error-badge{{border-color:#ff5252;color:#ff5252}}
.skins-card{{margin-bottom:16px}}
.skin-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(175px,1fr));gap:12px}}
.skin-item{{overflow:hidden;background:linear-gradient(145deg,#171b21,#0d1117);border:1px solid #70404a;border-radius:10px;min-width:0;box-shadow:0 5px 16px rgba(0,0,0,.2)}}
.skin-art{{height:125px;display:flex;align-items:center;justify-content:center;padding:12px;background:radial-gradient(circle at center,#242b35 0,#10161e 72%)}}
.skin-art img{{display:block;width:100%;height:100%;object-fit:contain;filter:drop-shadow(0 8px 8px rgba(0,0,0,.55))}}
.skin-placeholder{{color:#65717d;font-size:.75em}}
.skin-name{{min-height:46px;display:flex;align-items:center;justify-content:center;padding:9px 8px;border-top:1px solid #70404a;color:#ece8e1;font-size:.79em;font-weight:650;text-align:center}}
.empty-skins{{color:#8b978f;font-size:.85em}}
footer{{text-align:center;color:#8b978f;font-size:.78em;padding:20px;border-top:1px solid #2a3a4a;margin-top:20px}}
footer a{{color:#ff4655;text-decoration:none}}
@media(max-width:700px){{.two-col{{grid-template-columns:1fr}}.wallet-grid{{grid-template-columns:1fr 1fr}}}}
</style>
</head>
<body>
<header>
  <div class="brand">
    <svg class="logo" viewBox="0 0 32 32" fill="none"><circle cx="16" cy="16" r="16" fill="#ff4655"/><polygon points="16,6 22,12 16,18 10,12" fill="white"/><rect x="14" y="18" width="4" height="8" fill="white"/></svg>
    <span class="name">{game_name_esc}#{tag_line_esc}</span>
  </div>
  <div class="right">
    {f'<span class="cat-badge error-badge">{status_lbl_esc}</span>' if is_banned else f'<span class="cat-badge">{cat_label}</span>'}
    <span style="font-size:.85em;color:#8b978f">Level {r.level}</span>
  </div>
</header>
<main>
  {banned_banner}
  <div class="two-col">
    <div class="card">
      <h3>Thông tin tài khoản</h3>
      <div class="info-row"><span class="label">PUUID</span><span class="val small">{puuid_esc}</span></div>
      <div class="info-row"><span class="label">Level</span><span class="val">{r.level}</span></div>
      <div class="info-row"><span class="label">Region</span><span class="val">{region_esc}</span></div>
      <div class="info-row"><span class="label">Country</span><span class="val">{country_esc}</span></div>
      <div class="info-row"><span class="label">Email Verified</span><span class="val">{email_status}</span></div>
      <div class="info-row"><span class="label">Phone Verified</span><span class="val">{phone_status}</span></div>
      <div class="info-row"><span class="label">Account Created</span><span class="val">{r.created_at}</span></div>
      <div class="info-row"><span class="label">Status</span><span class="val">{status_badge}</span></div>
    </div>
    <div class="card">
      <h3>Wallet & Rank</h3>
      <div class="wallet-grid">
        <div class="wallet-card"><div class="val">{r.vp:,}</div><div class="lbl">VP</div></div>
        <div class="wallet-card"><div class="val">{r.rp:,}</div><div class="lbl">RP</div></div>
        <div class="wallet-card"><div class="val">{r.kc:,}</div><div class="lbl">KC</div></div>
      </div>
      <div class="info-row"><span class="label">Current Rank</span><span class="val">{rank_str}</span></div>
      <div class="stat-row">
        <div class="s"><span class="n">{r.skins_count}</span> <span class="l">Skins</span></div>
        <div class="s"><span class="n">{region_esc}</span> <span class="l">Region</span></div>
      </div>
    </div>
  </div>
  {skins_section}
  <div style="text-align:center;color:#8b978f;font-size:.78em;margin-top:12px">
    Checked: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
  </div>
</main>
<footer>Valorant Checker — Generated automatically</footer>
</body>
</html>"""


def save_results(
    results: list[Result],
    output_dir: Optional[Path] = None,
    run_dir: Optional[Path] = None,
) -> Path:
    """Lưu kết quả ra HTML + phân loại theo skin count."""
    if run_dir is None:
        ts = datetime.now().strftime("%d%m%Y_%H%M%S")
        run_dir = (output_dir or OUTPUT_DIR) / f"check_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # ── Phân loại tài khoản ──
    def _is_error(r: Result) -> bool:
        return not r.ok or r.status in (
            "banned", "time_ban", "flagged", "competitive_verify",
            "competitive_restricted", "error", "auth_fail",
            "email_verification", "wrong_credentials_or_legacy",
        )
    
    cat_email_verification = [r for r in results if r.status == "email_verification"]
    cat_wrong_login = [r for r in results if r.status == "wrong_credentials_or_legacy"]
    special_errors = {"email_verification", "wrong_credentials_or_legacy"}
    cat_error = [r for r in results if _is_error(r) and r.status not in special_errors]
    good = [r for r in results if not _is_error(r)]
    cat_0 = [r for r in good if r.skins_count == 0]
    cat_1_20 = [r for r in good if 1 <= r.skins_count <= 20]
    cat_21_60 = [r for r in good if 21 <= r.skins_count <= 60]
    cat_61_120 = [r for r in good if 61 <= r.skins_count <= 120]
    cat_120plus = [r for r in good if r.skins_count > 120]

    # Keep simple top-level account lists up to date after every completed check.
    active_accounts = [r for r in results if r.ok and r.status == "active"]
    dead_accounts = [r for r in results if not (r.ok and r.status == "active")]
    (run_dir / "active.txt").write_text(
        "\n".join(f"{r.username}:{r.password}" for r in active_accounts),
        encoding="utf-8",
    )
    (run_dir / "dead.txt").write_text(
        "\n".join(f"{r.username}:{r.password}" for r in dead_accounts),
        encoding="utf-8",
    )
    
    categories = [
        ("0_skins", "0 skins", cat_0, "#8b978f"),
        ("1-20_skins", "1-20 skins", cat_1_20, "#4caf50"),
        ("20-60_skins", "20-60 skins", cat_21_60, "#2196f3"),
        ("60-120_skins", "60-120 skins", cat_61_120, "#ff9800"),
        ("120+_skins", "120+ skins", cat_120plus, "#e91e63"),
        ("email_verification", "email verification", cat_email_verification, "#ffb74d"),
        ("wrong_credentials_or_legacy", "wrong login / legacy", cat_wrong_login, "#ef5350"),
        ("error", "error", cat_error, "#ff5252"),
    ]
    
    # Map kết quả tới tên thư mục phân loại để lưu file chi tiết
    result_to_cat_folder = {}
    
    # Lưu file phân loại (.txt) và tạo thư mục tương ứng
    logger.info("Saving categorized results to folders...")
    for fname, label, cat_list, _ in categories:
        if cat_list:
            cat_dir = run_dir / fname
            cat_dir.mkdir(parents=True, exist_ok=True)
            
            fpath = cat_dir / f"{fname}.txt"
            lines = [f"{r.username}:{r.password}" for r in cat_list]
            fpath.write_text("\n".join(lines), encoding="utf-8")
            logger.info(f"  Saved {len(cat_list)} accounts to {fname}/{fname}.txt")
            
            for r in cat_list:
                result_to_cat_folder[r.username] = fname
            
    # Lưu file chi tiết HTML từng account thành công vào đúng thư mục phân loại
    for r in results:
        if r.ok:
            cat_folder = result_to_cat_folder.get(r.username, "error")
            cat_dir = run_dir / cat_folder
            cat_dir.mkdir(parents=True, exist_ok=True)
            
            import re
            detail_fname = f"{r.game_name}_{r.tag_line}.html"
            detail_fname = re.sub(r'[\\/*?:"<>|]', "", detail_fname)
            detail_path = cat_dir / detail_fname
            detail_html = generate_account_html(r)
            detail_path.write_text(detail_html, encoding="utf-8")
    
    active = [r for r in results if r.ok and r.status == "active"]
    
    rows = ""
    for i, r in enumerate(results, 1):
        rank_name = RANK_NAMES[r.tier] if 0 <= r.tier < len(RANK_NAMES) else f"Rank {r.tier}"
        rank_str = f"{rank_name} - {r.rr}RR" if r.tier > 0 else "Unrated"
        
        if r.status == "active":
            cls = "ok"
        elif r.status in ("banned", "time_ban"):
            cls = "banned"
        elif r.status == "flagged":
            cls = "flagged"
        else:
            cls = "error"
            
        detail_link = "—"
        if r.ok:
            cat_folder = result_to_cat_folder.get(r.username, "error")
            import re
            detail_fname = f"{r.game_name}_{r.tag_line}.html"
            detail_fname = re.sub(r'[\\/*?:"<>|]', "", detail_fname)
            detail_link = f'<a href="{cat_folder}/{detail_fname}" target="_blank" style="color:#ff4655;font-weight:bold;text-decoration:none">Xem</a>'
        
        rows += f"""
        <tr>
            <td>{i}</td>
            <td>{r.username}</td>
            <td>{r.game_name}#{r.tag_line}</td>
            <td>{r.level}</td>
            <td style="color:#ff4655">{rank_str}</td>
            <td>{r.vp:,}</td>
            <td>{r.kc:,}</td>
            <td>{r.skins_count}</td>
            <td class="{cls}">{r.status_label}</td>
            <td>{detail_link}</td>
        </tr>"""
    
    # Tạo HTML stats cho các danh mục phân loại
    cat_stats_html = ""
    for _, label, cat_list, color in categories:
        cat_stats_html += f'        <div class="stat"><div class="n" style="color:{color}">{len(cat_list)}</div><div class="l">{label}</div></div>\n'
    
    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Valorant Check - {datetime.now():%d/%m/%Y %H:%M}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1923; color: #ece8e1; padding: 20px; }}
        h1 {{ color: #ff4655; margin-bottom: 20px; padding-bottom: 10px; border-bottom: 2px solid #ff4655; }}
        h2 {{ color: #ff4655; margin: 25px 0 15px 0; font-size: 1.2em; }}
        .stats {{ display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap; }}
        .stat {{ background: #1a2634; padding: 15px 25px; border-radius: 10px; text-align: center; min-width: 100px; }}
        .stat .n {{ font-size: 2em; font-weight: bold; color: #ff4655; }}
        .stat .l {{ color: #8b978f; font-size: 0.75em; text-transform: uppercase; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ text-align: left; padding: 12px; background: #1a2634; color: #8b978f; font-size: 0.75em; text-transform: uppercase; }}
        td {{ padding: 12px; background: #1a2634; margin-bottom: 4px; border-radius: 4px; }}
        tr:hover td {{ background: #243447; }}
        .ok {{ color: #4caf50; }}
        .banned {{ color: #ff5252; }}
        .flagged {{ color: #ff9800; }}
        .error {{ color: #ff5252; }}
        table a:hover {{ text-decoration: underline !important; }}
    </style>
</head>
<body>
    <h1>Valorant Account Check - {datetime.now():%d/%m/%Y %H:%M}</h1>
    
    <div class="stats">
        <div class="stat"><div class="n">{len(results)}</div><div class="l">Total</div></div>
        <div class="stat"><div class="n" style="color:#4caf50">{len(active)}</div><div class="l">Active</div></div>
        <div class="stat"><div class="n" style="color:#ff5252">{len(results)-len(active)}</div><div class="l">Errors/Banned</div></div>
    </div>
    
    <h2>📊 Skin Categories</h2>
    <div class="stats">
{cat_stats_html}    </div>
    
    <table>
        <thead>
            <tr>
                <th>#</th><th>Username</th><th>Name</th><th>Lv</th><th>Rank</th>
                <th>VP</th><th>KC</th><th>Skins</th><th>Status</th><th>Chi tiết</th>
            </tr>
        </thead>
        <tbody>{rows}
        </tbody>
    </table>
    
    <p style="color:#5a6670;font-size:0.75em;margin-top:20px;text-align:center">
        Generated by Valorant Checker - GoLogin Edition
    </p>
</body>
</html>"""
    
    path = run_dir / "index.html"
    path.write_text(html, encoding="utf-8")
    logger.info(f"Saved: {path}")
    return path


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def load_accounts(accounts_file: Optional[Path] = None) -> list[Account]:
    """Load accounts từ file."""
    source = accounts_file or ACCOUNTS_FILE
    if not source.exists():
        logger.error(f"File not found: {source}")
        source.write_text("""# Account format
# username:password:region:proxy:profile_id:ws_url
#
# Ví dụ:
# acc1@gmail.com:pass123:ap:http://user:pass@proxy:8080:profile123:
# acc2@gmail.com:pass456:eu::profile456:ws://localhost:9222
#
# - region: ap, na, eu, kr (mặc định: ap)
# - proxy: http://user:pass@host:port (để trống nếu không dùng)
# - profile_id: GoLogin Profile ID (từ app)
# - ws_url: WebSocket URL (để trống = tự động tìm)
""", encoding="utf-8")
        return []
    
    accounts = []
    seen_usernames: set[str] = set()
    duplicate_count = 0
    for line in source.read_text(encoding="utf-8").splitlines():
        acc = Account.parse(line)
        if acc:
            key = acc.username.strip().casefold()
            if key in seen_usernames:
                duplicate_count += 1
                continue
            seen_usernames.add(key)
            accounts.append(acc)

    if duplicate_count:
        logger.warning(f"Skipped {duplicate_count} duplicate account(s) by username")
    
    return accounts


def load_proxies(proxies_file: Optional[Path] = None) -> list[ProxyInfo]:
    """Load danh sách proxy từ proxies.txt.
    
    Format mỗi dòng: ip:port:user:pass hoặc ip:port
    Proxy được gán round-robin cho các account chưa có proxy.
    """
    source = proxies_file or PROXIES_FILE
    if not source.exists():
        logger.warning(f"Proxies file not found: {source}")
        return []
    proxies = []
    for line in source.read_text(encoding="utf-8").splitlines():
        p = ProxyInfo.parse(line)
        if p:
            proxies.append(p)
    return proxies


async def run_checker(
    accounts_file: Path = ACCOUNTS_FILE,
    proxies_file: Path = PROXIES_FILE,
    output_dir: Path = OUTPUT_DIR,
    concurrency: int = CONCURRENCY,
    browser_path: Path = GOLOGIN_BROWSER_PATH,
    extension_path: Optional[Path] = None,
    progress_callback: Optional[Callable[[Result, int, int], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> CheckerRunSummary:
    """Run checker with explicit paths so it can be embedded in the desktop app."""
    concurrency = max(1, int(concurrency))
    accounts_file = Path(accounts_file)
    proxies_file = Path(proxies_file)
    output_dir = Path(output_dir)
    browser_path = Path(browser_path)
    extension_path = Path(extension_path).resolve() if extension_path else None
    if extension_path and not (extension_path.is_dir() and (extension_path / "manifest.json").is_file()):
        raise ValueError(f"Extension folder must contain manifest.json: {extension_path}")
    profiles_dir = output_dir / ".temporary_profiles"
    run_dir = output_dir / f"check_{datetime.now():%d%m%Y_%H%M%S}"
    run_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 55)
    logger.info("  VALORANT CHECKER - GoLogin Edition")
    logger.info("=" * 55)
    logger.info(f"  Concurrency: {concurrency}")
    logger.info(f"  Output: {output_dir}")
    if extension_path:
        logger.info(f"  Extension: {extension_path}")
    logger.info("=" * 55)

    # Load accounts
    accounts = load_accounts(accounts_file)
    if not accounts:
        logger.error("No accounts found - check accounts.txt")
        return CheckerRunSummary(results=[], report_path=None)

    logger.info(f"Loaded {len(accounts)} accounts")

    # Load proxies từ proxies.txt
    proxies = load_proxies(proxies_file)
    if proxies:
        logger.info(f"Loaded {len(proxies)} proxies from {proxies_file}")
    else:
        logger.warning("No proxies loaded - all accounts will use direct connection")

    # Load Valorant skins map once for deduplication
    logger.info("Loading Valorant skins mapping from API...")
    await load_valorant_skins_map()

    # Gán proxy round-robin cho các account chưa có proxy
    sem = asyncio.Semaphore(concurrency)
    tasks: list[asyncio.Task[tuple[int, Result]]] = []

    async def run_one(index: int, account: Account, proxy_info: Optional[ProxyInfo]):
        result = await process_account(
            account,
            sem,
            proxy_info=proxy_info,
            browser_path=browser_path,
            profiles_dir=profiles_dir,
            extension_path=extension_path,
        )
        return index, result

    for i, acc in enumerate(accounts):
        pi = None
        if proxies and not acc.proxy:
            pi = proxies[i % len(proxies)]
            acc.proxy = pi.http_url  # Set cho httpx API calls
        tasks.append(asyncio.create_task(run_one(i, acc, pi)))

    pending = set(tasks)
    ordered_results: list[Optional[Result]] = [None] * len(accounts)
    completed_count = 0
    cancelled = False

    while pending:
        if cancel_event and cancel_event.is_set():
            cancelled = True
            logger.warning("Stop requested - closing active browsers...")
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            break

        done, pending = await asyncio.wait(
            pending,
            timeout=0.25,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in done:
            try:
                index, result = task.result()
            except asyncio.CancelledError:
                continue
            except Exception as exc:
                logger.error(f"Unhandled account task error: {exc}")
                continue

            ordered_results[index] = result
            completed_count += 1
            current_results = [item for item in ordered_results if item is not None]
            try:
                await asyncio.to_thread(save_results, current_results, output_dir, run_dir)
            except Exception as exc:
                logger.error(f"Cannot save incremental results: {exc}")
            if progress_callback:
                try:
                    progress_callback(result, completed_count, len(accounts))
                except Exception as exc:
                    logger.warning(f"Progress callback failed: {exc}")

    results = [result for result in ordered_results if result is not None]

    # Save
    report_path = save_results(results, output_dir, run_dir) if results else None

    # Summary
    active = sum(1 for r in results if r.ok and r.status == "active")
    banned = sum(1 for r in results if r.status in ("banned", "time_ban"))
    errors = sum(1 for r in results if not r.ok)
    logger.info("")
    logger.info("=" * 55)
    logger.info("  SUMMARY")
    logger.info("=" * 55)
    logger.info(f"  Total: {len(results)}")
    logger.info(f"  Active: {active}")
    logger.info(f"  Banned: {banned}")
    logger.info(f"  Errors: {errors}")
    logger.info(f"  Output: {output_dir}")
    logger.info("=" * 55)
    logger.info("  CANCELLED" if cancelled else "  DONE!")
    return CheckerRunSummary(results=results, report_path=report_path, cancelled=cancelled)


async def main():
    await run_checker()


if __name__ == "__main__":
    asyncio.run(main())
