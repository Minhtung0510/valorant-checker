# Valorant Checker — Python Edition

Tool tu dong dang nhap nhieu tai khoan Valorant bang Playwright, goi Riot API, xuat ket qua ra folder HTML.

## Setup

```bash
cd scripts/python
pip install -r requirements.txt
python -m playwright install chromium
```

## Hai cach chay

### Cach 1 — Chay nhieu tai khoan (file accounts.txt)

```bash
python main.py
```

### Cach 2 — Dung nhu module cho Discord bot (khuyen nghi)

```python
import asyncio
from checker import check_account

async def main():
    result = await check_account("email@domain.com", "password123", region="ap")

    if result.ok:
        print(f"✅ {result.game_name}#{result.tag_line}")
        print(f"   Rank: {result.rank_str}")
        print(f"   VP: {result.vp:,} | Skins: {result.skins_count}")
    else:
        print(f"❌ {result.status_label}: {result.ban_reason}")

asyncio.run(main())
```

Chi can goi `check_account()` — moi thu tu dong.

---

## File tai khoan (cho main.py)

Mo `accounts.txt`:

```
username@gmail.com:password123:ap
username2@riot.com:password456:na
```

Format: `username:password[:region]`
- `region`: `ap` (mac dinh), `na`, `eu`, `kr`

## Chay main.py

```bash
cd scripts/python
python main.py
```

## Ket qua

Sau khi chay xong, ket qua luu tai:
```
C:\Users\WORK\Desktop\Check-done\run_2026-06-01_12-00-00\
  ├── index.html        ← Mo file nay de xem tong hop
  ├── report.json       ← Bao cao JSON
  ├── 1-60_skins\    ← Account < 60 skin level
  ├── 60-120_skins\   ← Account 60-119 skin level
  ├── 120plus_skins\ ← Account 120+ skin level
  └── error\           ← Account loi
```

## Status codes

| Status | Y nghia |
|--------|---------|
| success | Thanh cong |
| wrong_password | Sai username/password |
| mfa_required | Account co 2FA — khong ho tro |
| captcha_required | Bi captcha, khong tu giai duoc |
| blocked | IP bi Riot chan — thu lai sau |
| error | Loi khac |

## Cau hinh (.env)

```env
OUTPUT_DIR=C:\Users\WORK\Desktop\Check-done
HEADLESS=false
DELAY_MIN=3
DELAY_MAX=6
```

## Cau truc project

```
scripts/python/
  main.py              ← Entry point (batch)
  checker.py           ← Module cho Discord bot (import duoc)
  auth.py              ← Playwright login + refresh token
  riot_api.py          ← Riot API (async httpx)
  sheets.py            ← File accounts + HTML output
  config.py            ← Constants, UUIDs
  accounts.txt         ← Danh sach tai khoan
  accounts.json        ← Token luu theo acc (auto tao, chua refresh_token)
  riot_session.json    ← Cookies da luu (tu dong tao)
  .env                 ← Cau hinh
  requirements.txt
  README.md
```

## Auth — 4 cach lay token (theo thu tu uu tien)

| Thu tu | Cach | Browser? | Token moi? | Khi nao |
|--------|------|----------|-----------|---------|
| 1 | Lockfile | Khong | ~1h | Valorant dang chay |
| 2 | Refresh token | Khong | ~1h (tu dong) | Da login lan dau |
| 3 | Full login | Co | ~1h | Lan dau tien / refresh fail |
| 4 | Lockfile fallback | Khong | ~1h | May chu |

**Sau lan dau login bang Playwright** → refresh_token luu vao `accounts.json` → **tu dong refresh** HTTP thuan → **khong can browser nua**.

**Doi mat khau** → refresh fail → xoa token trong accounts.json → tu dong re-login.

## Lưu ý

- Account co **2FA**: khong ho tro automation
- Refresh_token ton tai hang tuan — chi can login lai khi doi MK
- Khong chay qua nhieu account 1 lan — tot nhat 5-10 roi nghi
- Bi chan nhieu lan: doi IP hoac cho vai gio
