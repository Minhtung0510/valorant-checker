# Valorant Checker Desktop App

## Thành phần

- `ValorantChecker.exe`: app gửi cho khách hàng.
- `ValorantKeyManager.exe`: panel tạo key, chỉ admin giữ.
- `license_private_key.pem`: khóa bí mật của admin. Mất file này sẽ không thể tạo thêm key tương thích với app đã build.
- `license_public_key.pem`: được bundle trong client để xác minh key.

## Flow người dùng

1. Mở `ValorantChecker.exe`.
2. Copy Machine ID gửi admin.
3. Nhập license key do admin tạo.
4. Import file account, mỗi dòng `username:password` hoặc `username:password:region`.
5. Import proxy dạng `ip:port:user:password` hoặc `ip:port`.
6. Chọn Orbita `chrome.exe`, thư mục output và concurrency.
7. Nhấn **Bắt đầu**.
8. App mở browser, lấy token, đọc dữ liệu Riot, đóng browser và xóa profile tạm.
9. App xuất báo cáo HTML và bật nút **Mở HTML**.

## Tạo key

1. Mở `ValorantKeyManager.exe` trên máy admin.
2. Nhập khách hàng, số ngày sử dụng và Machine ID.
3. Nhấn **Tạo key**, sau đó copy key gửi khách.

Key được ký Ed25519. Client không chứa private key nên không thể tự tạo key hợp lệ. Key có thể khóa theo Machine ID và tự hết hạn theo thời gian đã đặt.

## Check proxy

1. Import file proxy dang `ip:port:user:password` hoac `ip:port`.
2. Chon thu muc output va concurrency.
3. Nhan **Check Proxy** de kiem tra realtime qua `api.ipify.org`.
4. Ket qua duoc chia thanh `live_proxies.txt`, `dead_proxies.txt` va `index.html` trong thu muc `proxy_check_<timestamp>`.

Timeout cua moi proxy la 12 giay. Nut **Dung** se ngung nhan them proxy moi va luu cac ket qua da hoan thanh.

## Build

Trong PowerShell:

```powershell
cd scripts\python
.\build_apps.ps1
```

Output:

```text
scripts\python\dist\
├── ValorantChecker\ValorantChecker.exe
└── ValorantKeyManager\ValorantKeyManager.exe
```

Chỉ phát hành thư mục `ValorantChecker`. Không phát hành Key Manager hoặc `license_private_key.pem`.

## Giới hạn bảo mật

Đây là license offline có chữ ký. Nó ngăn việc tự tạo hoặc chỉnh sửa key, hỗ trợ hết hạn và khóa máy. Vì không có license server, key đã phát hành không thể bị revoke từ xa; muốn revoke hoặc giới hạn số thiết bị theo thời gian thực cần backend online.
