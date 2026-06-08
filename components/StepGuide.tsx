"use client";

export function StepGuide() {
  return (
    <div className="space-y-6">
      <div className="card-bg p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-full bg-accent/20 text-accent flex items-center justify-center font-bold text-sm">
            0
          </div>
          <h3 className="text-lg font-semibold text-white">Đăng xuất tài khoản cũ</h3>
        </div>
        <p className="text-gray-400 text-sm mb-4">Trước tiên, hãy đăng xuất khỏi tài khoản Riot cũ (nếu có).</p>
        <a
          href="https://auth.riotgames.com/logout"
          target="_blank"
          rel="noopener noreferrer"
          className="btn-danger inline-flex items-center gap-2 text-sm"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>
          </svg>
          Đăng xuất
        </a>
      </div>

      <div className="card-bg p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-full bg-accent/20 text-accent flex items-center justify-center font-bold text-sm">
            1
          </div>
          <h3 className="text-lg font-semibold text-white">Đăng nhập Riot</h3>
        </div>
        <p className="text-gray-400 text-sm mb-4">
          Mở link đăng nhập bên dưới trong tab mới. Đăng nhập bằng tài khoản Valorant/ Riot của bạn.
        </p>
        <a
          href="https://auth.riotgames.com/authorize?redirect_uri=http://localhost/redirect&client_id=riot-client&response_type=token%20id_token&nonce=1&scope=openid%20link%20ban%20lol_region%20account"
          target="_blank"
          rel="noopener noreferrer"
          className="btn-primary inline-flex items-center gap-2 text-sm"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4M10 17l5-5-5-5M15 12H3"/>
          </svg>
          Mở trang đăng nhập Riot
        </a>
      </div>

      <div className="card-bg p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-full bg-accent/20 text-accent flex items-center justify-center font-bold text-sm">
            2
          </div>
          <h3 className="text-lg font-semibold text-white">Copy URL sau khi đăng nhập</h3>
        </div>
        <p className="text-gray-400 text-sm mb-4">
          Sau khi đăng nhập thành công, trình duyệt sẽ chuyển hướng sang <code className="text-cyan text-xs bg-black/30 px-1 py-0.5 rounded">localhost</code> 
          (kể cả khi báo lỗi 404 — đó là bình thường). Copy TOÀN BỘ URL trên thanh địa chỉ.
        </p>
        <div className="bg-black/40 border border-border rounded-lg p-3">
          <p className="text-gray-500 text-xs font-mono break-all">
            http://localhost/redirect#access_token=eyJ...&amp;scope=openid...&amp;id_token=eyJ...&amp;token_type=Bearer&amp;expires_in=3600
          </p>
        </div>
      </div>

      <div className="card-bg p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-8 h-8 rounded-full bg-accent/20 text-accent flex items-center justify-center font-bold text-sm">
            3
          </div>
          <h3 className="text-lg font-semibold text-white">Dán URL và tiến hành Check</h3>
        </div>
        <p className="text-gray-400 text-sm">
          Dán URL đã copy vào ô input bên dưới, chọn region, rồi bấm <span className="text-white font-semibold">&quot;Tiến hành Check&quot;</span>.
        </p>
      </div>
    </div>
  );
}
