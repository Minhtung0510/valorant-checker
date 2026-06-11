# Valorant Account Checker - GoLogin Edition

Tool kiểm tra nhiều tài khoản Valorant sử dụng **GoLogin browser** để tránh bị detect.

## Features

- **Multi-account**: Chạy nhiều accounts song song
- **Proxy riêng**: Mỗi account dùng proxy riêng
- **Fingerprint spoofing**: GoLogin spoof browser fingerprint
- **Cookies persistent**: Đăng nhập 1 lần, dùng lâu dài
- **Auto-reconnect**: Tự động kết nối lại nếu mất kết nối

## Setup

### 1. Cài đặt GoLogin

Tải và cài đặt GoLogin: https://gologin.com

### 2. Cài đặt Python dependencies

```bash
cd scripts/python
pip install -r requirements.txt
python -m playwright install chromium
```

### 3. Tạo GoLogin Profiles

Mỗi tài khoản Valorant cần 1 GoLogin Profile riêng:

1. Mở GoLogin App
2. Click **New Profile**
3. Điền thông tin:
   - **Name**: `Valorant_Email1` (tùy ý)
   - **OS**: Windows
   - **Browser**: Chromium
4. Setup Proxy (nếu cần):
   - Proxy Configuration → Add Proxy
   - Chọn proxy của bạn
5. **Đăng nhập Riot** trong profile đó:
   - Mở profile
   - Vào https://auth.riotgames.com
   - Login với tài khoản Valorant
6. Lặp lại cho mỗi account

### 4. Lấy Profile ID

Trong GoLogin, click vào profile → **Settings** → Copy **Profile ID**

## Cách sử dụng

### 1. Chỉnh sửa accounts.txt

```txt
# format: username:password:region:proxy:profile_id:ws_url

# Ví dụ với proxy:
acc1@gmail.com:pass123:ap:http://user:pass@proxyhost:8080:profile_id_here:

# Ví dụ không proxy:
acc2@gmail.com:pass456:eu::profile_id_here2:

# Ví dụ đầy đủ:
acc3@gmail.com:pass789:kr:http://user:pass@proxy:8080:abc123def:ws://localhost:9222
```

- `username`: Email đăng nhập Valorant
- `password`: Mật khẩu
- `region`: `ap`, `na`, `eu`, `kr` (mặc định: `ap`)
- `proxy`: Proxy format (để trống nếu không dùng)
- `profile_id`: GoLogin Profile ID (bắt buộc)
- `ws_url`: WebSocket URL (để trống = tự động tìm)

### 2. Chạy script

```bash
cd scripts/python
python main.py
```

## Config

Set environment variables:

```bash
# Số browser chạy song song (mặc định: 2)
set CONCURRENCY=2

# Output directory
set OUTPUT_DIR=C:\Users\WORK\Desktop\Check-done
```

## Output

Kết quả được lưu vào `OUTPUT_DIR`:

```
C:\Users\WORK\Desktop\Check-done\
├── index_20260610_120000.html  ← File tổng hợp
```

Mở file HTML để xem bảng kết quả với:
- Username, Game Name, Level
- Rank, VP, KC, Skins
- Status (Active/Error)

## Cách hoạt động

```
┌─────────────────────────────────────────────────────────────┐
│                      main.py                                 │
├─────────────────────────────────────────────────────────────┤
│  1. Đọc accounts.txt                                      │
│  2. Với mỗi account:                                       │
│     ├─ Kết nối GoLogin Browser (WebSocket/CDP)            │
│     ├─ Lấy tokens từ cookies (đã login sẵn)              │
│     ├─ Nếu không có → login trên browser                  │
│     └─ Gọi Riot API → lấy thông tin                       │
│  3. Lưu kết quả ra HTML                                   │
└─────────────────────────────────────────────────────────────┘
```

## Troubleshooting

### "Cannot connect to GoLogin"

1. Đảm bảo GoLogin đang chạy
2. Đảm bảo profile đã được mở (Start)
3. Kiểm tra Profile ID đúng chưa

### "Auth failed"

1. Mở GoLogin profile thủ công
2. Vào https://auth.riotgames.com
3. Đăng nhập lại Riot
4. Chạy lại script

### Proxy errors

1. Kiểm tra proxy còn hoạt động không
2. Format đúng: `http://user:pass@host:port`

## Files

```
scripts/python/
├── main.py           # Main script (GoLogin Edition)
├── accounts.txt     # Danh sách accounts
├── requirements.txt # Dependencies
├── README.md        # Documentation
└── logs/           # Log files
```

## Quick Start Checklist

- [ ] Cài GoLogin từ https://gologin.com
- [ ] Tạo GoLogin profile cho mỗi account
- [ ] Đăng nhập Riot trong mỗi profile
- [ ] Copy Profile ID từ GoLogin
- [ ] Điền thông tin vào accounts.txt
- [ ] Chạy `pip install -r requirements.txt`
- [ ] Chạy `python main.py`
- [ ] Xem kết quả trong thư mục Output
