"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { parseRedirectUrl } from "@/lib/parseRedirectUrl";
import type { Region } from "@/lib/types";

export default function HomePage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [region, setRegion] = useState<Region>("AP");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!url.trim()) {
      setError("Vui lòng dán URL redirect từ trình duyệt.");
      return;
    }

    const parsed = parseRedirectUrl(url);
    if (!parsed) {
      setError("URL không hợp lệ. Hãy đảm bảo bạn copy đầy đủ URL từ thanh địa chỉ, bao gồm phần #access_token.");
      return;
    }

    setIsLoading(true);

    try {
      const entitlementRes = await fetch("/api/riot/entitlement", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ accessToken: parsed.accessToken }),
      });

      if (!entitlementRes.ok) {
        const err = await entitlementRes.json();
        setError(err.error || "Lỗi khi lấy entitlement token.");
        setIsLoading(false);
        return;
      }

      const entitlementData = await entitlementRes.json();

      const userInfoRes = await fetch("/api/riot/userinfo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ accessToken: parsed.accessToken }),
      });

      if (!userInfoRes.ok) {
        const err = await userInfoRes.json();
        setError(err.error || "Lỗi khi lấy thông tin người dùng.");
        setIsLoading(false);
        return;
      }

      const userInfo = await userInfoRes.json();

      const expiresAt = Date.now() + parsed.expiresIn * 1000;

      router.push(
        `/dashboard?accessToken=${encodeURIComponent(parsed.accessToken)}` +
        `&entitlementToken=${encodeURIComponent(entitlementData.entitlements_token)}` +
        `&puuid=${encodeURIComponent(userInfo.sub)}` +
        `&gameName=${encodeURIComponent(userInfo.acct.game_name)}` +
        `&tagLine=${encodeURIComponent(userInfo.acct.tag_line)}` +
        `&region=${region}` +
        `&expiresAt=${expiresAt}`
      );
    } catch {
      setError("Đã xảy ra lỗi kết nối. Vui lòng thử lại.");
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-[#0a0a12]">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center gap-3">
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
            <circle cx="16" cy="16" r="16" fill="#ff4655"/>
            <polygon points="16,6 22,12 16,18 10,12" fill="white"/>
            <rect x="14" y="18" width="4" height="8" fill="white"/>
          </svg>
          <div>
            <h1 className="text-lg font-bold text-white">Valorant Checker</h1>
            <p className="text-xs text-gray-500">Kiểm tra tài khoản Valorant</p>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-8">
        {/* Hero */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-3 px-4 py-1.5 rounded-full text-xs font-semibold uppercase tracking-wider bg-accent/10 border border-accent/30 text-accent">
            <span className="w-2 h-2 rounded-full animate-pulse bg-accent" />
            Miễn phí - Không lưu token
          </div>
          <h2 className="text-3xl font-bold text-white mb-2">Check tài khoản Valorant</h2>
          <p className="text-gray-400">Xem rank, inventory, daily shop, wallet và kho đồ của bạn.</p>
        </div>

        {/* Features */}
        <div className="flex flex-wrap justify-center gap-3 mb-8">
          {["Rank / MMR", "Daily Shop", "Inventory", "Wallet", "Không cần đăng nhập", "Multi-account", "Đăng nhập dài hạn"].map((f) => (
            <span key={f} className="text-xs px-3 py-1.5 rounded-full bg-card border border-border text-gray-400">
              {f}
            </span>
          ))}
        </div>

        {/* Steps */}
        <div className="space-y-4 mb-8">
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ff4655" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>
            </svg>
            Hướng dẫn lấy Token
          </h3>

          {/* Step 0 */}
          <div className="card-bg p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold bg-accent/20 text-accent">0</div>
              <span className="font-semibold text-white">Đăng xuất tài khoản cũ</span>
            </div>
            <p className="text-sm text-gray-400 mb-3">Nếu đã đăng nhập Riot ở trình duyệt, hãy đăng xuất trước.</p>
            <a href="https://auth.riotgames.com/logout" target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-sm px-4 py-2 rounded bg-red-500/10 border border-red-500/40 text-red-400 hover:text-red-300 transition-colors">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>
              </svg>
              Đăng xuất
            </a>
          </div>

          {/* Step 1 */}
          <div className="card-bg p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold bg-accent/20 text-accent">1</div>
              <span className="font-semibold text-white">Đăng nhập Riot</span>
            </div>
            <p className="text-sm text-gray-400 mb-3">Mở link bên dưới trong tab mới, đăng nhập bằng tài khoản Valorant/Riot.</p>
            <a href="https://auth.riotgames.com/authorize?redirect_uri=http://localhost/redirect&client_id=riot-client&response_type=token%20id_token&nonce=1&scope=openid%20link%20ban%20lol_region%20account"
              target="_blank" rel="noopener noreferrer"
              className="btn-primary inline-flex items-center gap-2 text-sm">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4M10 17l5-5-5-5M15 12H3"/>
              </svg>
              Mở trang đăng nhập Riot
            </a>
          </div>

          {/* Step 2 */}
          <div className="card-bg p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold bg-accent/20 text-accent">2</div>
              <span className="font-semibold text-white">Copy URL sau khi đăng nhập</span>
            </div>
            <p className="text-sm text-gray-400 mb-2">
              Sau khi đăng nhập, trình duyệt chuyển sang <code className="text-cyan text-xs bg-black/30 px-1 py-0.5 rounded">localhost</code>. Copy toàn bộ URL trên thanh địa chỉ (kể cả lỗi 404).
            </p>
            <div className="rounded-lg p-3 text-xs font-mono bg-[#0f0f1a] border border-border text-gray-400 break-all">
              http://localhost/redirect#access_token=eyJ...&expires_in=3600
            </div>
          </div>
        </div>

        {/* Form */}
        <div className="card-bg p-6">
          <h3 className="text-base font-bold text-white mb-4 flex items-center gap-2">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" strokeWidth="2">
              <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
            </svg>
            Nhập Redirect URL
          </h3>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-gray-300 mb-2">Dán URL redirect từ Riot</label>
              <textarea
                className="w-full rounded-lg px-3 py-2 text-xs font-mono resize-none h-24 bg-[#0f0f1a] border border-border text-white placeholder-gray-600 focus:outline-none focus:border-accent transition-colors"
                placeholder="http://localhost/redirect#access_token=eyJ...&expires_in=3600"
                value={url}
                onChange={(e) => { setUrl(e.target.value); setError(""); }}
                disabled={isLoading}
              />
            </div>

            <div>
              <label className="block text-sm text-gray-300 mb-2">Chọn Region</label>
              <div className="flex gap-2 flex-wrap">
                {(["AP", "NA", "EU", "KR"] as Region[]).map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setRegion(r)}
                    disabled={isLoading}
                    className="px-4 py-1.5 rounded text-sm font-bold border transition-all"
                    style={{
                      background: region === r ? "rgba(255,70,85,0.2)" : "transparent",
                      borderColor: region === r ? "#ff4655" : "#2a2a3e",
                      color: region === r ? "#ff4655" : "#8b978f",
                    }}
                  >
                    {r}
                  </button>
                ))}
              </div>
            </div>

            {error && (
              <div className="rounded-lg px-4 py-3 text-sm bg-red-500/10 border border-red-500/40 text-red-400">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading || !url.trim()}
              className="btn-primary w-full py-3 font-bold text-white disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
            >
              {isLoading ? "Đang xử lý..." : "Tiến hành Check"}
            </button>

            <div className="text-center flex gap-3 justify-center flex-wrap">
              <a href="/bulk" className="text-xs px-4 py-2 rounded border inline-block text-gray-400 hover:text-white transition-colors" style={{ borderColor: "#2a2a3e" }}>
                Check nhiều tài khoản →
              </a>
              <a href="/auth" className="text-xs px-4 py-2 rounded border inline-block text-gray-400 hover:text-white transition-colors" style={{ borderColor: "#2a2a3e" }}>
                Đăng nhập dài hạn →
              </a>
            </div>

            <p className="text-center text-xs text-gray-600">
              Token chỉ được dùng trong phiên này, không được lưu bất kỳ đâu.
            </p>
          </form>
        </div>
      </main>
    </div>
  );
}
