"""
connect_to_chrome.py

Cach ket noi Playwright vao trinh duyet Chrome dang chay san (CDP).
Loi ich: Khong can mo trinh duyet moi, dung lai session da dang nhap.

HUONG DAN:
  1. Tat Tat ca cua so Chrome hien tai
  2. Mo Chrome voi remote debugging:
       "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
     Hoac tao shortcut:
       target: "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
  3. Dang nhap tai auth.riotgames.com trong trinh duyet do
  4. Chay: python connect_to_chrome.py

Playwright se dung trinh duyet Chrome dang chay, giu nguyen cookies/session.
"""
import asyncio
from playwright.async_api import async_playwright


async def test_chrome_connection():
    print("=== Test: Ket noi Playwright vao Chrome dang chay ===")
    print()

    async with async_playwright() as p:
        # Ket noi vao Chrome dang chay qua CDP
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        print(f"  Da ket noi! Browser: {browser}")

        # Lay context
        contexts = browser.contexts
        print(f"  So context: {len(contexts)}")

        if not contexts:
            print("  Loi: Khong co context nao!")
            await browser.disconnect()
            return

        context = contexts[0]
        pages = context.pages
        print(f"  So tab: {len(pages)}")

        # Thu truy cap auth.riotgames.com/userinfo
        for page in pages:
            print(f"  Tab: {page.url[:80]}")
            try:
                resp = await page.evaluate("""async () => {
                    const r = await fetch('https://auth.riotgames.com/userinfo', {
                        credentials: 'include'
                    });
                    return {status: r.status, url: r.url};
                }""")
                print(f"    /userinfo status: {resp}")
            except Exception as e:
                print(f"    /userinfo error: {e}")

        await browser.disconnect()
        print()
        print("OK")


if __name__ == "__main__":
    asyncio.run(test_chrome_connection())
