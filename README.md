# Valorant Checker

Tool kiểm tra thông tin tài khoản Valorant: rank, inventory, shop, wallet, purchase history, bulk check nhiều account cùng lúc.

## Cách khởi chạy (Web App)

```bash
npm install
npm run dev
# Mở http://localhost:3000
```

## Tính năng

### Check 1 tài khoản (`/`)

Truy cập trang chủ → paste redirect URL từ Riot → xem dashboard đầy đủ.

**Cách lấy redirect URL:**
1. Mở trình duyệt, đăng xuất Riot: https://auth.riotgames.com/logout
2. Truy cập: https://auth.riotgames.com/authorize?redirect_uri=http://localhost/redirect&client_id=riot-client&response_type=token%20id_token&nonce=1&scope=openid%20link%20ban%20lol_region%20account
3. Đăng nhập Riot
4. Copy toàn bộ URL (kể cả lỗi 404)
5. Paste vào tool

### Bulk Checker (`/bulk`)

Check nhiều account cùng lúc, phân loại theo skin level.

**Hỗ trợ 2 cách nhập liệu:**
- **Cách 1 — Tài khoản / Mật khẩu** (cần mở Valorant trước)
- **Cách 2 — Redirect URL**

**Phân loại tự động:**
- 🟠 1-60 Skins — dưới 60 skin level
- 🟢 60-120 Skins — 60-119 skin level
- 🟣 120+ Skins — từ 120 skin level trở lên
- 🔴 Lỗi / Bị Ban

---

## Full Automation — Python Edition (Playwright + Google Sheets)

Tool tự động hoàn toàn bằng Python. Đọc accounts từ Google Sheets, đăng nhập bằng Playwright, gọi Riot API, ghi kết quả ngược vào Google Sheets.

**Vị trí:** `scripts/python/`

### Cài đặt

```bash
cd scripts/python
pip install -r requirements.txt
python -m playwright install chromium
```

### Google Sheets Setup

**1. Tạo Google Cloud Project:**
- Vào https://console.cloud.google.com → Tạo project
- Enable **Google Sheets API**
- Vào **Credentials** → **Service Accounts** → Tạo mới
- Tải JSON key → đổi tên thành `credentials.json`, bỏ vào `scripts/python/`
- Copy **email** của Service Account

**2. Tạo Google Sheet:**
- Tạo Google Sheet mới
- Share Sheet với email Service Account (quyền Editor)
- Copy **Spreadsheet ID** từ URL

**3. Header Row 1:**

| Col | Header |
|-----|-------|
| A | username |
| B | password |
| C | region |
| D | game_name |
| E | tag_line |
| F | rank |
| G | vp |
| H | rp |
| I | kc |
| J | skins_count |
| K | access_token |
| L | token_expires_at |
| M | last_updated |
| N | status |

**4. Điền dữ liệu (Rows 2+):**
- Col A: `username@gmail.com`
- Col B: `password`
- Col C: `ap` (hoặc `na`, `eu`, `kr`)

**5. Cấu hình `.env`:**
```env
SPREADSHEET_ID=1ABC...xyz
GOOGLE_CREDS_PATH=credentials.json
HEADLESS=false
DELAY_MIN=3
DELAY_MAX=6
```

### Chạy

```bash
cd scripts/python
python main.py
```

### Status codes

| Status | Ý nghĩa |
|--------|---------|
| success | Thành công |
| wrong_password | Sai username/password |
| mfa_required | Account có 2FA — không hỗ trợ |
| captcha_required | Bị captcha, không tự giải |
| blocked | IP bị Riot chặn — thử lại sau |
| error | Lỗi khác |

### Cấu trúc project Python

```
scripts/python/
  main.py        ← Entry point
  auth.py        ← Playwright login flow
  riot_api.py    ← Riot API (async httpx)
  sheets.py     ← Google Sheets read/write
  config.py     ← Constants, UUIDs
  .env          ← Cấu hình
  credentials.json  ← Google Service Account key
  requirements.txt
  README.md
```

---

## Đã hoàn thành

- [x] Check rank / MMR
- [x] Check wallet (VP, RP, KC, Free Agents)
- [x] Check inventory (Skins, Agents, Cards, Buddies, Sprays)
- [x] Check daily shop
- [x] Check account XP / level
- [x] Check user info (country, email, phone, ban status)
- [x] Purchase history tab
- [x] Skin Levels count trong skins stats bar
- [x] Bulk check nhiều account cùng lúc
- [x] Phân loại account theo skin level (1-60 / 60-120 / 120+)
- [x] Export HTML cho từng account (dashboard style)
- [x] Export tất cả HTML (index + folder)
- [x] Bulk check bằng username:password (Riot Client API)
- [x] Python automation tool (Playwright + Riot API + Google Sheets)
- [x] Giao diện dark theme Valorant style

## Đang làm

- [ ] Test & fix Python automation tool

## Lưu ý

- Token chỉ được dùng trong phiên, không lưu ở đâu
- Account có 2FA: không hỗ trợ automation — dùng cách paste redirect URL
- Riot Client API: cần mở Valorant trước khi check
