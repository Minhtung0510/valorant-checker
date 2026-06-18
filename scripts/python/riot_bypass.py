"""
riot_bypass.py — Client Python gọi captcha-solver-ai HTTP API để bypass Riot captcha.

CÁCH HOẠT ĐỘNG:
    1. App checker gặp `data.captcha: true` từ Riot.
    2. Gọi RiotBypassClient.solve(cookies) → POST tới captcha-solver-ai server.
    3. Server mở puppeteer-stealth browser, dùng Vision AI giải challenge (nếu có).
    4. Trả về cookies mới + token.

USAGE:
    from riot_bypass import RiotBypassClient

    client = RiotBypassClient("http://127.0.0.1:7711")
    result = await client.solve({"clid": "...", "ssid": "..."}, username="acc1")
    if result.ok:
        # Cập nhật cookie_dict với result.cookies
        ...

CẦN:
    - captcha-solver-ai app đang chạy (npm start)
    - Server API bật (mặc định port 7711)
    - Ollama + qwen2.5vl đang chạy (cho Vision AI)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("riot_bypass")


@dataclass
class RiotBypassResult:
    ok: bool
    method: str  # 'cookie_reuse' | 'vision_ai' | 'stealth_browser' | 'failed'
    token: Optional[str] = None
    cookies: Optional[Dict[str, str]] = None
    details: Optional[str] = None
    screenshot_base64: Optional[str] = None
    elapsed_ms: int = 0

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> "RiotBypassResult":
        return cls(
            ok=bool(data.get("ok")),
            method=str(data.get("method", "failed")),
            token=data.get("token"),
            cookies=data.get("cookies"),
            details=data.get("details"),
            screenshot_base64=data.get("screenshotBase64"),
            elapsed_ms=int(data.get("elapsedMs", 0)),
        )


class RiotBypassClient:
    """Client cho captcha-solver-ai HTTP server (port 7711)."""

    def __init__(
        self,
        server_url: str = "http://127.0.0.1:7711",
        timeout: float = 90.0,
        enabled: Optional[bool] = None,
    ):
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        # Auto-detect enabled from env. Default: bật.
        if enabled is None:
            enabled = os.getenv("RIOT_BYPASS_ENABLED", "1") not in ("0", "false", "False")
        self.enabled = enabled

    async def is_ready(self) -> bool:
        if not self.enabled:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                r = await c.get(f"{self.server_url}/riot-status")
                if r.is_success:
                    data = r.json()
                    logger.info("riot_bypass ready: %s", data)
                    return True
                return False
        except Exception as e:
            logger.debug("riot_bypass not ready: %s", e)
            return False

    async def solve(
        self,
        cookies: Dict[str, str],
        username: Optional[str] = None,
        max_wait_ms: Optional[int] = None,
        challenge_url: Optional[str] = None,
    ) -> RiotBypassResult:
        """
        Yêu cầu server giải captcha Riot với cookies đã cho.
        Trả về RiotBypassResult.ok=True nếu thành công.
        """
        if not self.enabled:
            return RiotBypassResult(ok=False, method="disabled", details="RIOT_BYPASS_ENABLED=0")

        payload: Dict[str, Any] = {
            "cookies": cookies,
            "headless": True,
        }
        if username:
            payload["username"] = username
        if max_wait_ms:
            payload["maxWaitMs"] = max_wait_ms
        if challenge_url:
            payload["challengeUrl"] = challenge_url

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                r = await c.post(f"{self.server_url}/riot-solve", json=payload)
                if not r.is_success:
                    logger.warning("riot_bypass HTTP %s: %s", r.status_code, r.text[:200])
                    return RiotBypassResult(
                        ok=False, method="failed",
                        details=f"HTTP {r.status_code}: {r.text[:200]}",
                    )
                data = r.json()
                result = RiotBypassResult.from_api(data)
                if result.ok:
                    logger.info(
                        "riot_bypass OK method=%s elapsed=%dms details=%s",
                        result.method, result.elapsed_ms, result.details,
                    )
                else:
                    logger.warning(
                        "riot_bypass FAIL method=%s elapsed=%dms details=%s",
                        result.method, result.elapsed_ms, result.details,
                    )
                return result
        except httpx.ConnectError:
            logger.warning(
                "riot_bypass: cannot connect to %s — is captcha-solver-ai running?",
                self.server_url,
            )
            return RiotBypassResult(
                ok=False, method="failed",
                details=f"connection error: {self.server_url}",
            )
        except Exception as e:
            logger.error("riot_bypass exception: %s", e)
            return RiotBypassResult(ok=False, method="failed", details=str(e))


# === Singleton pattern cho app checker ===
_client_singleton: Optional[RiotBypassClient] = None


def get_bypass_client() -> RiotBypassClient:
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = RiotBypassClient(
            server_url=os.getenv("RIOT_BYPASS_URL", "http://127.0.0.1:7711"),
            timeout=float(os.getenv("RIOT_BYPASS_TIMEOUT", "90")),
        )
    return _client_singleton
