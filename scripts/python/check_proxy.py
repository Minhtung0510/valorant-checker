"""
check_proxy.py — Kiểm tra proxy có live không.
Usage: python check_proxy.py [proxy_file]
"""

import asyncio
import sys
import re
from pathlib import Path


def parse_proxy(proxy: str) -> dict:
    """Parse proxy string."""
    proxy = proxy.strip()
    if not proxy:
        return {}

    if proxy.startswith("http://") or proxy.startswith("https://"):
        return {"server": proxy}

    # host:port:user:pass format
    if proxy.count(":") >= 3:
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

    return {"server": f"http://{proxy}"}


async def check_proxy(proxy: str) -> tuple[str, bool, str]:
    """Check single proxy. Returns (proxy, is_alive, message)."""
    try:
        import httpx

        parsed = parse_proxy(proxy)
        if not parsed:
            return proxy, False, "Invalid format"

        server = parsed["server"]
        proxies = {"http://": server, "https://": server}

        async with httpx.AsyncClient(timeout=10.0, proxies=proxies) as client:
            r = await client.get("https://httpbin.org/ip")
            if r.status_code == 200:
                ip = r.json().get("origin", "unknown")
                return proxy, True, f"OK - IP: {ip}"
            else:
                return proxy, False, f"Status: {r.status_code}"

    except Exception as e:
        return proxy, False, str(e)[:80]


async def check_all(proxies: list[str]) -> None:
    """Check all proxies concurrently."""
    print(f"Checking {len(proxies)} proxy...\n")
    print(f"{'Proxy':<50} {'Status':<15} {'Info'}")
    print("-" * 80)

    tasks = [check_proxy(p) for p in proxies]
    results = await asyncio.gather(*tasks)

    live_count = 0
    for proxy, is_alive, msg in results:
        status = "✅ LIVE" if is_alive else "❌ DEAD"
        short = proxy.split("@")[-1] if "@" in proxy else proxy
        print(f"{short:<50} {status:<15} {msg}")
        if is_alive:
            live_count += 1

    print(f"\n{'='*80}")
    print(f"Result: {live_count}/{len(proxies)} proxy LIVE")


def main():
    # Load proxies
    proxy_file = Path("proxies.txt")
    if len(sys.argv) > 1:
        proxy_file = Path(sys.argv[1])

    if not proxy_file.exists():
        # Check common locations
        for path in ["proxies.txt", "proxies.txt", "../proxies.txt", "../../proxies.txt"]:
            p = Path(path)
            if p.exists():
                proxy_file = p
                break

    if not proxy_file.exists():
        print(f"Error: proxies.txt not found")
        print("Usage: python check_proxy.py [proxy_file]")
        sys.exit(1)

    # Parse proxies
    proxies = []
    for line in proxy_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        proxies.append(line)

    if not proxies:
        print("No proxies found in file")
        sys.exit(1)

    # Check
    asyncio.run(check_all(proxies))


if __name__ == "__main__":
    main()
