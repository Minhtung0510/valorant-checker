"use client";

import { useState, useEffect, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import type { Region } from "@/lib/types";

interface SessionInfo {
  sessionId: string;
  gameName: string;
  tagLine: string;
  puuid: string;
  region: string;
  createdAt: string;
  expiresAt: string;
  isExpired: boolean;
}

interface RefreshedTokens {
  accessToken: string;
  entitlementToken: string;
  expiresAt: number;
}

export default function AuthPage() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const [region, setRegion] = useState<Region>("AP");
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [refreshingId, setRefreshingId] = useState<string | null>(null);

  const redirectUri = typeof window !== "undefined"
    ? `${window.location.origin}/api/auth/callback`
    : "http://localhost:3000/api/auth/callback";

  // Handle callback redirect with session ID
  useEffect(() => {
    const sid = searchParams.get("sid");
    const reg = searchParams.get("region");
    const err = searchParams.get("error");
    if (err) {
      setError(`Đăng nhập thất bại: ${err}`);
    }
    if (sid) {
      // Immediately refresh token for this session so dashboard can use it
      handleRefreshAndGo(sid, reg || "AP");
    }
  }, [searchParams]);

  // Load saved sessions
  const loadSessions = useCallback(async () => {
    try {
      const res = await fetch("/api/auth/sessions");
      if (!res.ok) return;
      const data = await res.json();
      setSessions(data.sessions ?? []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // Refresh token for a session, then navigate to dashboard
  const handleRefreshAndGo = async (sessionId: string, reg: string) => {
    setRefreshingId(sessionId);
    try {
      const refreshRes = await fetch("/api/auth/refresh", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId }),
      });

      if (!refreshRes.ok) {
        setError("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
        await loadSessions();
        return;
      }

      const tokens = await refreshRes.json() as RefreshedTokens;
      router.push(
        `/dashboard?sessionId=${encodeURIComponent(sessionId)}` +
        `&accessToken=${encodeURIComponent(tokens.accessToken)}` +
        `&entitlementToken=${encodeURIComponent(tokens.entitlementToken)}` +
        `&expiresAt=${tokens.expiresAt}` +
        `&region=${reg}`
      );
    } catch {
      setError("Không thể kết nối. Vui lòng thử lại.");
    } finally {
      setRefreshingId(null);
    }
  };

  // Start Riot auth flow (authorization code)
  const handleLogin = () => {
    const authUrl = new URL("https://auth.riotgames.com/authorize");
    authUrl.searchParams.set("redirect_uri", redirectUri);
    authUrl.searchParams.set("client_id", "riot-client");
    authUrl.searchParams.set("response_type", "code");
    authUrl.searchParams.set("scope", "openid link ban lol_region account");
    authUrl.searchParams.set("state", region); // pass region as state
    authUrl.searchParams.set("nonce", "1");
    window.location.href = authUrl.toString();
  };

  // Delete a session
  const handleDelete = async (sessionId: string) => {
    if (!confirm("Xóa phiên đăng nhập này?")) return;
    await fetch("/api/auth/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId }),
    });
    await loadSessions();
  };

  const handleGoDashboard = async (session: SessionInfo) => {
    if (session.isExpired) {
      if (!confirm("Phiên đăng nhập đã hết hạn. Xóa và đăng nhập lại?")) return;
      await handleDelete(session.sessionId);
      await loadSessions();
      return;
    }
    setActiveSessionId(session.sessionId);
    await handleRefreshAndGo(session.sessionId, session.region);
  };

  return (
    <div className="min-h-screen" style={{ background: "#0f1923", color: "#ece8e1", fontFamily: "'Segoe UI', system-ui, sans-serif" }}>
      {/* Header */}
      <header style={{ borderBottom: "2px solid #ff4655" }}>
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
              <circle cx="16" cy="16" r="16" fill="#ff4655"/>
              <polygon points="16,6 22,12 16,18 10,12" fill="white"/>
              <rect x="14" y="18" width="4" height="8" fill="white"/>
            </svg>
            <span className="font-bold text-white">Đăng nhập dài hạn</span>
          </div>
          <a href="/" className="text-xs px-3 py-1.5 rounded border text-gray-400 hover:text-white" style={{ borderColor: "#2a3a4a" }}>
            Trang chủ
          </a>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8">

        {/* ── Error Banner ── */}
        {error && (
          <div className="mb-6 p-4 rounded-lg flex items-center justify-between" style={{ background: "rgba(183,28,28,0.3)", border: "1px solid #b71c1c" }}>
            <div className="flex items-center gap-3">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#ff5252" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>
              </svg>
              <span style={{ color: "#ff5252", fontSize: "0.9em" }}>{error}</span>
            </div>
            <button onClick={() => setError("")} style={{ color: "#ff5252", background: "none", border: "none", cursor: "pointer", fontSize: "1.1em", lineHeight: 1 }}>✕</button>
          </div>
        )}

        {/* ── Explanation ── */}
        <div className="card-bg p-6 mb-6">
          <h2 className="text-xl font-bold text-white mb-2 flex items-center gap-2">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>
            </svg>
            Tài khoản đăng nhập dài hạn
          </h2>
          <p className="text-sm" style={{ color: "#8b978f", lineHeight: 1.7 }}>
            Khác với đăng nhập thông thường (token 1 tiếng), phương pháp này sử dụng <strong style={{ color: "#ece8e1" }}>refresh token</strong> —
            token sống được cho đến khi bạn đổi mật khẩu Riot.
            Token được lưu trong file <code style={{ background: "#0f0f1a", padding: "1px 5px", borderRadius: 4, fontSize: "0.88em", color: "#00d4ff" }}>scripts/python/auth_sessions.json</code> trên server.
          </p>
        </div>

        {/* ── Setup Instructions ── */}
        <div className="card-bg p-6 mb-6">
          <h3 className="text-base font-bold text-white mb-4 flex items-center gap-2">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ff4655" strokeWidth="2">
              <polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>
            </svg>
            Cấu hình Redirect URI
          </h3>

          <div className="space-y-3">
            <div className="flex items-start gap-3">
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 mt-0.5" style={{ background: "rgba(255,70,85,0.2)", color: "#ff4655" }}>1</div>
              <div>
                <p className="text-sm font-semibold text-white mb-1">Thêm Redirect URI trên Riot Developer</p>
                <p className="text-xs mb-2" style={{ color: "#8b978f" }}>Truy cập trang quản lý ứng dụng Riot và thêm URI bên dưới vào danh sách redirect:</p>
                <div className="rounded-lg p-3 font-mono text-xs break-all" style={{ background: "#0f0f1a", border: "1px solid #2a3a4a", color: "#00d4ff" }}>
                  {redirectUri}
                </div>
                <a href="https://auth.riotgames.com/manage/organizations" target="_blank" rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 mt-2 text-xs px-3 py-1.5 rounded" style={{ background: "rgba(255,70,85,0.1)", border: "1px solid rgba(255,70,85,0.3)", color: "#ff4655" }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3"/>
                  </svg>
                  auth.riotgames.com/manage/organizations
                </a>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 mt-0.5" style={{ background: "rgba(255,70,85,0.2)", color: "#ff4655" }}>2</div>
              <div>
                <p className="text-sm font-semibold text-white mb-1">Cấp quyền ứng dụng</p>
                <p className="text-xs" style={{ color: "#8b978f" }}>
                  Nếu chưa có ứng dụng, tạo mới với loại <strong style={{ color: "#ece8e1" }}>\"Riot Client\"</strong>.
                  Sau đó bấm <strong style={{ color: "#ece8e1" }}>\"New Redirect URI\"</strong> và dán URI ở trên.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 mt-0.5" style={{ background: "rgba(255,70,85,0.2)", color: "#ff4655" }}>3</div>
              <div>
                <p className="text-sm font-semibold text-white mb-1">Chọn region &amp; Đăng nhập</p>
                <p className="text-xs" style={{ color: "#8b978f" }}>
                  Chọn region của bạn bên dưới, bấm <strong style={{ color: "#ece8e1" }}>"Đăng nhập với Riot"</strong>, cấp quyền, và bạn sẽ quay lại trang này với phiên đăng nhập dài hạn.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* ── Login Form ── */}
        <div className="card-bg p-6 mb-6">
          <h3 className="text-base font-bold text-white mb-4">Đăng nhập với Riot</h3>

          <div className="flex gap-3 flex-wrap items-end">
            <div>
              <label className="block text-xs mb-2" style={{ color: "#8b978f" }}>Region</label>
              <div className="flex gap-2">
                {(["AP", "NA", "EU", "KR"] as Region[]).map((r) => (
                  <button key={r} onClick={() => setRegion(r)}
                    className="px-4 py-2 rounded text-sm font-bold border transition-all cursor-pointer"
                    style={{
                      background: region === r ? "rgba(255,70,85,0.2)" : "transparent",
                      borderColor: region === r ? "#ff4655" : "#2a3a4a",
                      color: region === r ? "#ff4655" : "#8b978f",
                    }}>
                    {r}
                  </button>
                ))}
              </div>
            </div>

            <button onClick={handleLogin}
              className="px-6 py-2 rounded font-bold text-white transition-all flex items-center gap-2 cursor-pointer"
              style={{ background: "#ff4655", border: "1px solid #ff4655" }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" fill="#ff4655"/>
                <polygon points="12,6 16,10 12,14 8,10" fill="white"/>
                <rect x="10" y="14" width="4" height="4" fill="white"/>
              </svg>
              Đăng nhập với Riot
            </button>
          </div>
        </div>

        {/* ── Saved Sessions ── */}
        <div className="card-bg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" strokeWidth="2">
                <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/>
                <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/>
              </svg>
              Tài khoản đã lưu
              {!loading && sessions.length > 0 && (
                <span className="text-xs px-2 py-0.5 rounded font-normal" style={{ background: "#1a2634", color: "#8b978f" }}>
                  {sessions.length}
                </span>
              )}
            </h3>
            <button onClick={loadSessions} className="text-xs px-3 py-1 rounded border text-gray-400 hover:text-white cursor-pointer" style={{ borderColor: "#2a3a4a" }}>
              ↻ Làm mới
            </button>
          </div>

          {loading ? (
            <div className="text-center py-8 text-sm" style={{ color: "#8b978f" }}>Đang tải...</div>
          ) : sessions.length === 0 ? (
            <div className="text-center py-8">
              <div className="text-4xl mb-3">📭</div>
              <p className="text-sm" style={{ color: "#8b978f" }}>Chưa có tài khoản nào được lưu.</p>
              <p className="text-xs mt-1" style={{ color: "#5a6670" }}>Đăng nhập bên trên để bắt đầu.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {sessions.map((session) => (
                <div key={session.sessionId}
                  className="rounded-lg p-4 flex items-center gap-4 flex-wrap"
                  style={{ background: "#0d1520", border: "1px solid #2a3a4a" }}>

                  {/* Avatar placeholder */}
                  <div className="w-10 h-10 rounded-full flex items-center justify-center text-lg flex-shrink-0" style={{ background: "rgba(255,70,85,0.2)" }}>
                    🎮
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold text-white">{session.gameName}#{session.tagLine}</span>
                      <span className="text-xs px-2 py-0.5 rounded" style={{ background: "#1a2634", color: "#8b978f" }}>{session.region}</span>
                      {session.isExpired && (
                        <span className="text-xs px-2 py-0.5 rounded font-semibold" style={{ background: "rgba(255,82,82,0.15)", color: "#ff5252" }}>Hết hạn</span>
                      )}
                    </div>
                    <div className="flex gap-4 mt-1 text-xs" style={{ color: "#5a6670" }}>
                      <span>Đăng nhập: {session.createdAt}</span>
                      <span>Hết hạn: {session.expiresAt}</span>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-2 flex-shrink-0">
                    <button
                      onClick={() => handleGoDashboard(session)}
                      disabled={refreshingId === session.sessionId || activeSessionId === session.sessionId}
                      className="px-4 py-1.5 rounded text-sm font-bold text-white transition-all flex items-center gap-1 cursor-pointer"
                      style={{ background: "#ff4655", opacity: (refreshingId === session.sessionId || activeSessionId === session.sessionId) ? 0.6 : 1 }}>
                      {refreshingId === session.sessionId || activeSessionId === session.sessionId ? (
                        <>
                          <div className="w-3 h-3 border border-white border-t-transparent rounded-full animate-spin"/>
                          Đang mở...
                        </>
                      ) : (
                        <>
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 9h6v6H9z"/>
                          </svg>
                          Mở Dashboard
                        </>
                      )}
                    </button>
                    <button
                      onClick={() => handleDelete(session.sessionId)}
                      className="px-3 py-1.5 rounded text-sm text-gray-400 hover:text-red-400 transition-all border cursor-pointer"
                      style={{ borderColor: "#2a3a4a" }}>
                      ✕
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── Footer Note ── */}
        <div className="mt-6 p-4 rounded-lg text-center text-xs" style={{ background: "#0d1520", border: "1px solid #2a3a4a", color: "#5a6670" }}>
          <p>Refresh token sẽ sống đến khi bạn đổi mật khẩu Riot. Token được lưu trong file JSON trên server — không ai khác có thể truy cập.</p>
        </div>
      </main>
    </div>
  );
}
