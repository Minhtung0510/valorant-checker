"use client";

import { useState, useEffect } from "react";
import { parseRedirectUrl } from "@/lib/parseRedirectUrl";

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

interface BulkResult {
  success: boolean;
  error?: string;
  region: string;
  puuid?: string;
  gameName: string;
  tagLine: string;
  level?: number;
  currentRank?: number;
  currentRR?: number;
  valorantPoints?: number;
  radianitePoints?: number;
  kingdomCredits?: number;
  freeAgents?: number;
  levelCount?: number;
  createdAt?: string | null;
  accountStatus?: string;
  country?: string | null;
  emailVerified?: boolean;
  phoneVerified?: boolean;
}

type Category = "1-60" | "60-120" | "120+" | "error";

const CATEGORY_LABELS: Record<Category, string> = {
  "1-60": "1-60 Skins",
  "60-120": "60-120 Skins",
  "120+": "120+ Skins",
  error: "Lỗi / Bị Ban",
};

const CATEGORY_COLORS: Record<Category, string> = {
  "1-60": "#f5a623",
  "60-120": "#4caf50",
  "120+": "#9c27b0",
  error: "#ff5252",
};

function getCategory(result: BulkResult): Category {
  if (!result.success) return "error";
  const count = result.levelCount ?? 0;
  if (count < 60) return "1-60";
  if (count < 120) return "60-120";
  return "120+";
}

const RANK_NAMES = [
  "Unrated","Iron 1","Iron 2","Iron 3",
  "Bronze 1","Bronze 2","Bronze 3",
  "Silver 1","Silver 2","Silver 3",
  "Gold 1","Gold 2","Gold 3",
  "Platinum 1","Platinum 2","Platinum 3",
  "Diamond 1","Diamond 2","Diamond 3",
  "Ascendant 1","Ascendant 2","Ascendant 3",
  "Immortal 1","Immortal 2","Immortal 3",
  "Radiant",
];

function rankLabel(tier: number): string {
  return RANK_NAMES[tier] ?? `Rank ${tier}`;
}

function h(s: string | undefined | null): string {
  if (!s) return "";
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function generateAccountHtml(result: BulkResult): string {
  const cat = getCategory(result);
  const catLabel = CATEGORY_LABELS[cat];
  const catColor = CATEGORY_COLORS[cat];
  const tier = result.currentRank ?? 0;
  const rr = result.currentRR ?? 0;
  const rank = tier > 0 ? rankLabel(tier) : "—";
  const isBanned = result.accountStatus && result.accountStatus !== "Active";

  return `<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${h(result.gameName)}#${h(result.tagLine)} - Valorant Checker</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f1923;color:#ece8e1;font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh}
header{background:#1a2634;border-bottom:2px solid #ff4655;padding:16px 24px;display:flex;align-items:center;justify-content:space-between}
header .brand{display:flex;align-items:center;gap:12px}
header .brand .logo{width:36px;height:36px}
header .brand .name{font-size:1.2em;font-weight:700;color:#ff4655;letter-spacing:1px}
header .right{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
main{max-width:1100px;margin:0 auto;padding:20px 24px}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}
.card{background:#1a2634;border:1px solid #2a3a4a;border-radius:10px;padding:16px}
.card h3{color:#ff4655;font-size:.72em;text-transform:uppercase;letter-spacing:.8px;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #2a3a4a}
.info-row{display:flex;padding:7px 0;border-bottom:1px solid rgba(42,58,74,.3);font-size:.88em;gap:10px}
.info-row:last-child{border-bottom:none}
.info-row .label{color:#8b978f;min-width:130px;flex-shrink:0}
.info-row .val{font-weight:600;color:#ece8e1;word-break:break-all}
.info-row .val.small{font-size:.75em}
.green-badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.8em;font-weight:600;background:#1b5e20;color:#4caf50}
.red-badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:.8em;font-weight:600;background:#2a1a1a;color:#ff5252}
.wallet-grid{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;margin-bottom:12px}
.wallet-card{background:#0d1520;border:1px solid #2a3a4a;border-radius:8px;padding:10px;text-align:center}
.wallet-card .val{font-size:1.1em;font-weight:700;color:#ff4655}
.wallet-card .lbl{font-size:.68em;color:#8b978f;text-transform:uppercase;letter-spacing:.5px;margin-top:2px}
.stat-row{display:flex;gap:16px;padding-top:8px;border-top:1px solid #2a3a4a}
.stat-row .s{font-size:.88em}
.stat-row .s .n{font-weight:700;color:#ece8e1}
.stat-row .s .l{color:#8b978f;font-size:.8em}
.cat-badge{display:inline-block;padding:3px 12px;border-radius:12px;font-size:.8em;font-weight:700;border:1px solid ${catColor};color:${catColor};background:transparent}
.cat-badge.error-badge{border-color:#ff5252;color:#ff5252}
footer{text-align:center;color:#8b978f;font-size:.78em;padding:20px;border-top:1px solid #2a3a4a;margin-top:20px}
footer a{color:#ff4655;text-decoration:none}
@media(max-width:700px){.two-col{grid-template-columns:1fr}.wallet-grid{grid-template-columns:1fr 1fr}}
</style>
</head>
<body>
<header>
  <div class="brand">
    <svg class="logo" viewBox="0 0 32 32" fill="none"><circle cx="16" cy="16" r="16" fill="#ff4655"/><polygon points="16,6 22,12 16,18 10,12" fill="white"/><rect x="14" y="18" width="4" height="8" fill="white"/></svg>
    <span class="name">${h(result.gameName)}#${h(result.tagLine)}</span>
  </div>
  <div class="right">
    ${isBanned
      ? `<span class="cat-badge error-badge">${h(result.accountStatus ?? "BANNED")}</span>`
      : `<span class="cat-badge">${catLabel}</span>`
    }
    <span style="font-size:.85em;color:#8b978f">Level ${result.level ?? "—"}</span>
  </div>
</header>
<main>
  ${isBanned ? `<div style="background:rgba(183,28,28,.2);border:1px solid #b71c1c;border-radius:8px;padding:14px;margin-bottom:16px;color:#ff5252;font-weight:600">⚠ Account bị: ${h(result.accountStatus ?? "BANNED")}</div>` : ""}
  <div class="two-col">
    <div class="card">
      <h3>Thông tin tài khoản</h3>
      <div class="info-row"><span class="label">PUUID</span><span class="val small">${h(result.puuid)}</span></div>
      <div class="info-row"><span class="label">Level</span><span class="val">${result.level ?? "—"}</span></div>
      <div class="info-row"><span class="label">Region</span><span class="val">${h(result.region?.toUpperCase())}</span></div>
      <div class="info-row"><span class="label">Country</span><span class="val">${result.country ? h(result.country.toUpperCase()) : "—"}</span></div>
      <div class="info-row"><span class="label">Email Verified</span><span class="val">${result.emailVerified ? "Yes" : "No"}</span></div>
      <div class="info-row"><span class="label">Phone Verified</span><span class="val">${result.phoneVerified ? "Yes" : "No"}</span></div>
      <div class="info-row"><span class="label">Account Created</span><span class="val">${result.createdAt ?? "—"}</span></div>
      <div class="info-row"><span class="label">Status</span><span class="val">${result.accountStatus === "Active" ? "<span class='green-badge'>Active</span>" : `<span class='red-badge'>${h(result.accountStatus ?? "Unknown")}</span>`}</span></div>
    </div>
    <div class="card">
      <h3>Wallet & Rank</h3>
      <div class="wallet-grid">
        <div class="wallet-card"><div class="val">${result.valorantPoints?.toLocaleString() ?? "—"}</div><div class="lbl">VP</div></div>
        <div class="wallet-card"><div class="val">${result.radianitePoints?.toLocaleString() ?? "—"}</div><div class="lbl">RP</div></div>
        <div class="wallet-card"><div class="val">${result.kingdomCredits?.toLocaleString() ?? "—"}</div><div class="lbl">KC</div></div>
        <div class="wallet-card"><div class="val">${result.freeAgents?.toLocaleString() ?? "—"}</div><div class="lbl">FA</div></div>
      </div>
      <div class="info-row"><span class="label">Current Rank</span><span class="val">${rank}${rr > 0 ? ` (${rr} RR)` : ""}</span></div>
      <div class="stat-row">
        <div class="s"><span class="n">${result.levelCount ?? "—"}</span> <span class="l">Skin Levels</span></div>
        <div class="s"><span class="n">${result.region?.toUpperCase()}</span> <span class="l">Region</span></div>
      </div>
    </div>
  </div>
  <div style="text-align:center;color:#8b978f;font-size:.78em;margin-top:12px">
    Checked: ${new Date().toLocaleString("vi-VN")}
  </div>
</main>
<footer>Valorant Checker — Generated automatically</footer>
</body>
</html>`;
}

function downloadBlob(content: string, filename: string) {
  const blob = new Blob([content], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function downloadAll(results: BulkResult[]) {
  // Create index page
  const categorized: Record<Category, BulkResult[]> = { "1-60": [], "60-120": [], "120+": [], error: [] };
  for (const r of results) categorized[getCategory(r)].push(r);

  const rows: string[] = [];
  for (const [cat, catResults] of Object.entries(categorized) as [Category, BulkResult[]][]) {
    if (catResults.length === 0) continue;
    rows.push(`<div class="cat"><h2><span class="dot" style="background:${CATEGORY_COLORS[cat]}"></span>${CATEGORY_LABELS[cat]} (${catResults.length})</h2>
    <table><thead><tr><th>#</th><th>Account</th><th>Level</th><th>VP</th><th>Skin Levels</th><th>Status</th><th>File</th></tr></thead><tbody>
    ${catResults.map((r, i) => `<tr>
      <td>${i + 1}</td>
      <td>${r.gameName}#${r.tagLine}</td>
      <td>${r.level ?? "—"}</td>
      <td>${r.valorantPoints?.toLocaleString() ?? "—"}</td>
      <td>${r.levelCount ?? "—"}</td>
      <td><span class="badge" style="background:${r.accountStatus === "Active" ? "#1b5e20" : "#2a1a1a"};color:${r.accountStatus === "Active" ? "#4caf50" : "#ff5252"}">${r.accountStatus ?? "—"}</span></td>
      <td>${r.success ? `<a href="${r.gameName}_${r.tagLine}.html" download>Tải</a>` : "—"}</td>
    </tr>`).join("")}
    </tbody></table></div>`);
  }

  const indexHtml = `<!DOCTYPE html>
<html lang="vi">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Valorant Bulk Check Results</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f1923;color:#ece8e1;font-family:'Segoe UI',system-ui,sans-serif;padding:20px}
h1{color:#ff4655;font-size:1.4em;margin-bottom:16px;padding-bottom:10px;border-bottom:2px solid #ff4655}
.cat{margin-bottom:24px}
.cat h2{font-size:.85em;text-transform:uppercase;letter-spacing:.5px;color:#8b978f;margin-bottom:8px;display:flex;align-items:center;gap:8px}
.cat h2 .dot{width:10px;height:10px;border-radius:50%}
.cat table{width:100%;border-collapse:separate;border-spacing:0 4px}
.cat table th{text-align:left;color:#8b978f;font-size:.72em;text-transform:uppercase;padding:6px 10px}
.cat table td{background:#1a2634;padding:8px 10px;font-size:.85em;border-radius:6px}
.cat table tr:hover td{background:#243447}
.cat table a{color:#ff4655;text-decoration:none;font-weight:600}
.cat table a:hover{text-decoration:underline}
.summary{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:24px}
.summary .s{background:#1a2634;border:1px solid #2a3a4a;border-radius:10px;padding:12px 16px}
.summary .s .n{font-size:1.3em;font-weight:700;color:#ff4655}
.summary .s .l{font-size:.72em;color:#8b978f;text-transform:uppercase}
</style>
</head>
<body>
<h1>Valorant Bulk Check — ${new Date().toLocaleString("vi-VN")}</h1>
<div class="summary">
  ${Object.entries(categorized).map(([cat, catResults]) => `<div class="s"><div class="n">${catResults.length}</div><div class="l">${CATEGORY_LABELS[cat as Category]}</div></div>`).join("")}
</div>
${rows.join("")}
</body>
</html>`;

  downloadBlob(indexHtml, `valorant_bulk_${Date.now()}.html`);
  for (const r of results) {
    if (r.success) {
      downloadBlob(generateAccountHtml(r), `${r.gameName}_${r.tagLine}.html`);
    }
  }
}

export default function BulkPage() {
  const [input, setInput] = useState("");
  const [region, setRegion] = useState("AP");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<BulkResult[]>([]);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<"token" | "auth" | "session">("session");
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [selectedSessionIds, setSelectedSessionIds] = useState<string[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState(false);

  // Load saved sessions on mount
  useEffect(() => {
    const loadSessions = async () => {
      setSessionsLoading(true);
      try {
        const res = await fetch("/api/auth/sessions");
        if (res.ok) {
          const data = await res.json();
          setSessions(data.sessions ?? []);
        }
      } catch { /* ignore */ }
      setSessionsLoading(false);
    };
    loadSessions();
  }, []);

  const categorized: Record<Category, BulkResult[]> = { "1-60": [], "60-120": [], "120+": [], error: [] };
  for (const r of results) categorized[getCategory(r)].push(r);

  const toggleSession = (sessionId: string) => {
    setSelectedSessionIds((prev) =>
      prev.includes(sessionId) ? prev.filter((id) => id !== sessionId) : [...prev, sessionId]
    );
  };

  const handleCheck = async () => {
    const lines = input.split("\n").map((l) => l.trim()).filter(Boolean);
    setError("");

    if (mode === "session") {
      if (selectedSessionIds.length === 0) {
        setError("Chọn ít nhất 1 session để check.");
        return;
      }
      setLoading(true);
      setDone(false);
      try {
        const res = await fetch("/api/riot/bulk", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sessionIds: selectedSessionIds }),
        });
        if (res.ok) {
          const data = await res.json();
          setResults(data.results ?? []);
        } else {
          setError(`Lỗi server: ${res.status}`);
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Lỗi kết nối");
      } finally {
        setLoading(false);
        setDone(true);
      }
      return;
    }

    if (mode === "auth") {
      // Login via Riot Client local API
      const credentials: Array<{ username: string; password: string }> = [];
      for (const line of lines) {
        const idx = line.indexOf(":");
        if (idx > 0) {
          credentials.push({ username: line.slice(0, idx), password: line.slice(idx + 1) });
        }
      }
      if (credentials.length === 0) {
        setError("Định dạng không đúng. Dùng: username:password");
        return;
      }

      setLoading(true);
      setDone(false);

      const loginRes = await Promise.allSettled(
        credentials.map(async (cred) => {
          const res = await fetch("/api/riot/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(cred),
          });
          return { ...(await res.json()), username: cred.username };
        })
      );

      const successLogins = loginRes
        .filter((r): r is PromiseFulfilledResult<Record<string, unknown>> =>
          r.status === "fulfilled" && !!(r.value as Record<string, unknown>).accessToken)
        .map((r) => ({ accessToken: (r.value as { accessToken: string }).accessToken, region }));

      const loginErrors = loginRes
        .filter((r) => r.status !== "fulfilled" || !(r.value as Record<string, unknown>).accessToken)
        .map((r) => ({
          success: false,
          error: r.status === "rejected" ? (r.reason?.message ?? "Login failed") : ((r.value as Record<string, unknown>).error as string) ?? "Login failed",
          region,
          gameName: r.status === "fulfilled" ? (r.value as { username: string }).username : "Unknown",
          tagLine: "",
        }));

      if (successLogins.length === 0) {
        setResults(loginErrors as BulkResult[]);
        setLoading(false);
        setDone(true);
        return;
      }

      try {
        const bulkRes = await fetch("/api/riot/bulk", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ accounts: successLogins }),
        });
        const data = await bulkRes.json();
        setResults([...(data.results ?? []), ...loginErrors] as BulkResult[]);
      } finally {
        setLoading(false);
        setDone(true);
      }
      return;
    }

    // Token mode
    const accounts: Array<{ accessToken: string; region: string }> = [];
    for (const line of lines) {
      const parsed = parseRedirectUrl(line);
      if (parsed) accounts.push({ accessToken: parsed.accessToken, region });
    }
    if (accounts.length === 0) {
      setError("Không tìm thấy access token hợp lệ trong dữ liệu nhập vào.");
      return;
    }

    setLoading(true);
    setDone(false);

    try {
      const res = await fetch("/api/riot/bulk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ accounts }),
      });
      if (res.ok) {
        const data = await res.json();
        setResults(data.results ?? []);
      } else {
        setError(`Lỗi server: ${res.status}`);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Lỗi kết nối");
    } finally {
      setLoading(false);
      setDone(true);
    }
  };

  const successCount = results.filter((r) => r.success).length;

  return (
    <div style={{ minHeight: "100vh", background: "#0f1923", color: "#ece8e1", fontFamily: "'Segoe UI',system-ui,sans-serif" }}>
      {/* Header */}
      <header style={{ background: "#1a2634", borderBottom: "2px solid #ff4655" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "12px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <svg width="30" height="30" viewBox="0 0 32 32" fill="none">
              <circle cx="16" cy="16" r="16" fill="#ff4655"/>
              <polygon points="16,6 22,12 16,18 10,12" fill="white"/>
              <rect x="14" y="18" width="4" height="8" fill="white"/>
            </svg>
            <span style={{ fontWeight: 700, color: "#ff4655", fontSize: "1.1em", letterSpacing: "0.5px" }}>Valorant Bulk Checker</span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <a href="/" style={{ fontSize: "0.8em", padding: "5px 12px", border: "1px solid #2a3a4a", borderRadius: 6, color: "#8b978f", textDecoration: "none" }}>
              Check 1 tài khoản
            </a>
          </div>
        </div>
      </header>

      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "20px 24px" }}>
        {/* Input card */}
        <div style={{ background: "#1a2634", border: "1px solid #2a3a4a", borderRadius: 12, padding: 24, marginBottom: 20 }}>
          {/* Mode tabs */}
          <div style={{ display: "flex", gap: 8, marginBottom: 16, borderBottom: "1px solid #2a3a4a", paddingBottom: 12 }}>
            <button
              onClick={() => { setMode("auth"); setInput(""); setError(""); }}
              style={{
                padding: "6px 16px", borderRadius: 6, fontSize: "0.82em", fontWeight: 700,
                border: `1px solid ${mode === "auth" ? "#ff4655" : "#2a3a4a"}`,
                background: mode === "auth" ? "rgba(255,70,85,0.2)" : "transparent",
                color: mode === "auth" ? "#ff4655" : "#8b978f",
                cursor: "pointer",
              }}
            >
              Tài khoản / Mật khẩu
            </button>
            <button
              onClick={() => { setMode("token"); setInput(""); setError(""); }}
              style={{
                padding: "6px 16px", borderRadius: 6, fontSize: "0.82em", fontWeight: 700,
                border: `1px solid ${mode === "token" ? "#ff4655" : "#2a3a4a"}`,
                background: mode === "token" ? "rgba(255,70,85,0.2)" : "transparent",
                color: mode === "token" ? "#ff4655" : "#8b978f",
                cursor: "pointer",
              }}
            >
              Redirect URL
            </button>
          </div>

          {/* Mode tabs */}
          <div style={{ display: "flex", gap: 8, marginBottom: 16, borderBottom: "1px solid #2a3a4a", paddingBottom: 12 }}>
            <button
              onClick={() => { setMode("session"); setInput(""); setError(""); }}
              style={{
                padding: "6px 16px", borderRadius: 6, fontSize: "0.82em", fontWeight: 700,
                border: `1px solid ${mode === "session" ? "#ff4655" : "#2a3a4a"}`,
                background: mode === "session" ? "rgba(255,70,85,0.2)" : "transparent",
                color: mode === "session" ? "#ff4655" : "#8b978f",
                cursor: "pointer",
              }}
            >
              Saved Sessions
            </button>
            <button
              onClick={() => { setMode("auth"); setInput(""); setError(""); }}
              style={{
                padding: "6px 16px", borderRadius: 6, fontSize: "0.82em", fontWeight: 700,
                border: `1px solid ${mode === "auth" ? "#ff4655" : "#2a3a4a"}`,
                background: mode === "auth" ? "rgba(255,70,85,0.2)" : "transparent",
                color: mode === "auth" ? "#ff4655" : "#8b978f",
                cursor: "pointer",
              }}
            >
              Tài khoản / Mật khẩu
            </button>
            <button
              onClick={() => { setMode("token"); setInput(""); setError(""); }}
              style={{
                padding: "6px 16px", borderRadius: 6, fontSize: "0.82em", fontWeight: 700,
                border: `1px solid ${mode === "token" ? "#ff4655" : "#2a3a4a"}`,
                background: mode === "token" ? "rgba(255,70,85,0.2)" : "transparent",
                color: mode === "token" ? "#ff4655" : "#8b978f",
                cursor: "pointer",
              }}
            >
              Redirect URL
            </button>
          </div>

          {/* ─── SESSION MODE ─── */}
          {mode === "session" && (
            <div>
              <h2 style={{ fontWeight: 700, color: "#ece8e1", marginBottom: 6 }}>Saved Sessions</h2>
              <p style={{ fontSize: "0.82em", color: "#8b978f", marginBottom: 14 }}>
                Chọn các tài khoản đã lưu từ trang <a href="/auth" style={{ color: "#ff4655", textDecoration: "none" }}>Đăng nhập dài hạn</a>.
                Token sẽ được tự động refresh khi cần thiết.
              </p>

              {sessionsLoading ? (
                <div style={{ textAlign: "center", padding: "20px", color: "#8b978f", fontSize: "0.85em" }}>Đang tải sessions...</div>
              ) : sessions.length === 0 ? (
                <div style={{ textAlign: "center", padding: "20px", color: "#5a6670", fontSize: "0.85em" }}>
                  Chưa có session nào.{" "}
                  <a href="/auth" style={{ color: "#ff4655", textDecoration: "none" }}>Đăng nhập tại đây</a>.
                </div>
              ) : (
                <div style={{ marginBottom: 14 }}>
                  {sessions.map((s) => (
                    <div
                      key={s.sessionId}
                      onClick={() => toggleSession(s.sessionId)}
                      style={{
                        display: "flex", alignItems: "center", gap: 12, padding: "10px 14px",
                        marginBottom: 6, borderRadius: 8, cursor: "pointer",
                        background: selectedSessionIds.includes(s.sessionId) ? "rgba(255,70,85,0.12)" : "#0d1520",
                        border: `1px solid ${selectedSessionIds.includes(s.sessionId) ? "#ff4655" : "#2a3a4a"}`,
                      }}
                    >
                      {/* Checkbox */}
                      <div style={{
                        width: 18, height: 18, borderRadius: 4, flexShrink: 0,
                        border: `2px solid ${selectedSessionIds.includes(s.sessionId) ? "#ff4655" : "#2a3a4a"}`,
                        background: selectedSessionIds.includes(s.sessionId) ? "#ff4655" : "transparent",
                        display: "flex", alignItems: "center", justifyContent: "center",
                      }}>
                        {selectedSessionIds.includes(s.sessionId) && (
                          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3">
                            <polyline points="20 6 9 17 4 12"/>
                          </svg>
                        )}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                          <span style={{ fontWeight: 700, fontSize: "0.9em" }}>{s.gameName}#{s.tagLine}</span>
                          <span style={{ fontSize: "0.72em", padding: "1px 7px", borderRadius: 4, background: "#1a2634", color: "#8b978f" }}>{s.region}</span>
                          {s.isExpired && (
                            <span style={{ fontSize: "0.72em", padding: "1px 7px", borderRadius: 4, background: "rgba(255,82,82,0.15)", color: "#ff5252" }}>Hết hạn</span>
                          )}
                        </div>
                        <div style={{ fontSize: "0.72em", color: "#5a6670", marginTop: 2 }}>
                          Hết hạn: {s.expiresAt}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                <span style={{ fontSize: "0.82em", color: "#8b978f" }}>
                  {selectedSessionIds.length > 0 ? `Đã chọn: ${selectedSessionIds.length} session(s)` : "Chưa chọn session nào"}
                </span>
                <button
                  onClick={handleCheck}
                  disabled={loading || selectedSessionIds.length === 0}
                  style={{
                    marginLeft: "auto", padding: "8px 24px", borderRadius: 8, fontWeight: 700,
                    background: "#ff4655", border: "1px solid #ff4655", color: "#fff",
                    cursor: loading || selectedSessionIds.length === 0 ? "not-allowed" : "pointer",
                    opacity: loading || selectedSessionIds.length === 0 ? 0.5 : 1,
                  }}
                >
                  {loading ? "Đang check..." : `Check ${selectedSessionIds.length} tài khoản`}
                </button>
              </div>
            </div>
          )}

          {/* ─── AUTH MODE ─── */}
          {mode === "auth" && (
            <div>
              <h2 style={{ fontWeight: 700, color: "#ece8e1", marginBottom: 6 }}>Danh sách Tài khoản</h2>
              <p style={{ fontSize: "0.82em", color: "#8b978f", marginBottom: 14 }}>
                Mỗi dòng: username:password. Cần mở Valorant trước (kể cả chỉ chạy nền).
              </p>
              <textarea
                value={input}
                onChange={(e) => { setInput(e.target.value); setError(""); }}
                placeholder="nakki123@gmail.com:password123&#10;dual1ty#natly:secretpass"
                style={{
                  width: "100%", background: "#0d1520", border: "1px solid #2a3a4a", borderRadius: 8,
                  color: "#ece8e1", fontFamily: "monospace", fontSize: "0.8em",
                  padding: "10px 12px", resize: "vertical", outline: "none", minHeight: 140,
                }}
              />
              {error && (
                <div style={{ marginTop: 10, padding: "10px 14px", background: "rgba(183,28,28,.2)", border: "1px solid #b71c1c", borderRadius: 8, color: "#ff5252", fontSize: "0.85em" }}>
                  {error}
                </div>
              )}
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 14, flexWrap: "wrap" }}>
                <span style={{ fontSize: "0.8em", color: "#8b978f" }}>Region:</span>
                {(["AP", "NA", "EU", "KR"] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => setRegion(r)}
                    style={{
                      padding: "5px 14px", borderRadius: 6, fontSize: "0.82em", fontWeight: 700,
                      border: `1px solid ${region === r ? "#ff4655" : "#2a3a4a"}`,
                      background: region === r ? "rgba(255,70,85,0.2)" : "transparent",
                      color: region === r ? "#ff4655" : "#8b978f",
                      cursor: "pointer",
                    }}
                  >
                    {r}
                  </button>
                ))}
                <button
                  onClick={handleCheck}
                  disabled={loading || !input.trim()}
                  style={{
                    marginLeft: "auto", padding: "8px 24px", borderRadius: 8, fontWeight: 700,
                    background: "#ff4655", border: "1px solid #ff4655", color: "#fff",
                    cursor: loading || !input.trim() ? "not-allowed" : "pointer",
                    opacity: loading || !input.trim() ? 0.5 : 1,
                  }}
                >
                  {loading ? "Đang check..." : `Check ${input.split("\n").filter((l) => l.trim()).length} tài khoản`}
                </button>
              </div>
            </div>
          )}

          {/* ─── TOKEN MODE ─── */}
          {mode === "token" && (
            <div>
              <h2 style={{ fontWeight: 700, color: "#ece8e1", marginBottom: 6 }}>Danh sách Redirect URL</h2>
              <p style={{ fontSize: "0.82em", color: "#8b978f", marginBottom: 14 }}>
                Mỗi dòng 1 redirect URL từ Riot. Cách lấy: mở auth.riotgames.com, đăng nhập, copy URL sau khi chuyển trang.
              </p>
              <textarea
                value={input}
                onChange={(e) => { setInput(e.target.value); setError(""); }}
                placeholder="http://localhost/redirect#access_token=eyJ...&#10;http://localhost/redirect#access_token=eyJ..."
                style={{
                  width: "100%", background: "#0d1520", border: "1px solid #2a3a4a", borderRadius: 8,
                  color: "#ece8e1", fontFamily: "monospace", fontSize: "0.8em",
                  padding: "10px 12px", resize: "vertical", outline: "none", minHeight: 140,
                }}
              />
              {error && (
                <div style={{ marginTop: 10, padding: "10px 14px", background: "rgba(183,28,28,.2)", border: "1px solid #b71c1c", borderRadius: 8, color: "#ff5252", fontSize: "0.85em" }}>
                  {error}
                </div>
              )}
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 14, flexWrap: "wrap" }}>
                <span style={{ fontSize: "0.8em", color: "#8b978f" }}>Region:</span>
                {(["AP", "NA", "EU", "KR"] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => setRegion(r)}
                    style={{
                      padding: "5px 14px", borderRadius: 6, fontSize: "0.82em", fontWeight: 700,
                      border: `1px solid ${region === r ? "#ff4655" : "#2a3a4a"}`,
                      background: region === r ? "rgba(255,70,85,0.2)" : "transparent",
                      color: region === r ? "#ff4655" : "#8b978f",
                      cursor: "pointer",
                    }}
                  >
                    {r}
                  </button>
                ))}
                <button
                  onClick={handleCheck}
                  disabled={loading || !input.trim()}
                  style={{
                    marginLeft: "auto", padding: "8px 24px", borderRadius: 8, fontWeight: 700,
                    background: "#ff4655", border: "1px solid #ff4655", color: "#fff",
                    cursor: loading || !input.trim() ? "not-allowed" : "pointer",
                    opacity: loading || !input.trim() ? 0.5 : 1,
                  }}
                >
                  {loading ? "Đang check..." : `Check ${input.split("\n").filter((l) => l.trim()).length} tài khoản`}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Results */}
        {done && (
          <>
            {/* Summary */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 20 }}>
              {(Object.entries(categorized) as [Category, BulkResult[]][]).map(([cat, catResults]) => (
                <div key={cat} style={{ background: "#1a2634", border: `1px solid ${CATEGORY_COLORS[cat]}`, borderRadius: 10, padding: 16, textAlign: "center" }}>
                  <div style={{ fontSize: "1.8em", fontWeight: 700, color: CATEGORY_COLORS[cat] }}>{catResults.length}</div>
                  <div style={{ fontSize: "0.68em", color: CATEGORY_COLORS[cat], opacity: 0.8, textTransform: "uppercase", letterSpacing: "0.5px", marginTop: 4 }}>{CATEGORY_LABELS[cat]}</div>
                </div>
              ))}
            </div>

            {/* Download all */}
            {results.length > 0 && (
              <button
                onClick={() => downloadAll(results)}
                style={{ marginBottom: 20, padding: "10px 24px", borderRadius: 8, fontWeight: 700, background: "#4caf50", border: "1px solid #4caf50", color: "#fff", cursor: "pointer" }}
              >
                Tải tất cả HTML ({successCount} file + index)
              </button>
            )}

            {/* Category sections */}
            {(Object.entries(categorized) as [Category, BulkResult[]][]).map(([cat, catResults]) =>
              catResults.length > 0 && (
                <div key={cat} style={{ marginBottom: 24 }}>
                  <h3 style={{ fontWeight: 700, marginBottom: 10, display: "flex", alignItems: "center", gap: 8, color: CATEGORY_COLORS[cat] }}>
                    <span style={{ width: 10, height: 10, borderRadius: "50%", background: CATEGORY_COLORS[cat], display: "inline-block" }} />
                    {CATEGORY_LABELS[cat]} ({catResults.length})
                  </h3>
                  <div style={{ overflowX: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "separate", borderSpacing: "0 4px" }}>
                      <thead>
                        <tr>
                          {["#", "Account", "Level", "VP", "RP", "Skin Levels", "Status", "Action"].map((h) => (
                            <th key={h} style={{ textAlign: "left", color: "#8b978f", fontSize: "0.72em", textTransform: "uppercase", letterSpacing: "0.5px", padding: "6px 10px" }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {catResults.map((r, i) => (
                          <tr key={i}>
                            <td style={{ background: "#1a2634", padding: "8px 10px", borderRadius: "6px 0 0 6px", color: CATEGORY_COLORS[cat], fontWeight: 700, textAlign: "center", width: 40 }}>{i + 1}</td>
                            <td style={{ background: "#1a2634", padding: "8px 10px", fontWeight: 600 }}>{r.gameName}#{r.tagLine}</td>
                            <td style={{ background: "#1a2634", padding: "8px 10px" }}>{r.level ?? "—"}</td>
                            <td style={{ background: "#1a2634", padding: "8px 10px", color: "#ff4655", fontWeight: 700 }}>{r.valorantPoints?.toLocaleString() ?? "—"}</td>
                            <td style={{ background: "#1a2634", padding: "8px 10px" }}>{r.radianitePoints?.toLocaleString() ?? "—"}</td>
                            <td style={{ background: "#1a2634", padding: "8px 10px" }}>{r.levelCount ?? "—"}</td>
                            <td style={{ background: "#1a2634", padding: "8px 10px" }}>
                              <span style={{ display: "inline-block", padding: "1px 7px", borderRadius: 4, fontSize: "0.8em", fontWeight: 600, background: r.accountStatus === "Active" ? "#1b5e20" : "#2a1a1a", color: r.accountStatus === "Active" ? "#4caf50" : "#ff5252" }}>
                                {r.success ? (r.accountStatus ?? "Active") : r.error}
                              </span>
                            </td>
                            <td style={{ background: "#1a2634", padding: "8px 10px", borderRadius: "0 6px 6px 0" }}>
                              {r.success && (
                                <button
                                  onClick={() => downloadBlob(generateAccountHtml(r), `${r.gameName}_${r.tagLine}.html`)}
                                  style={{ padding: "3px 10px", borderRadius: 5, fontSize: "0.78em", fontWeight: 700, background: "#ff4655", border: "none", color: "#fff", cursor: "pointer" }}
                                >
                                  HTML
                                </button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )
            )}
          </>
        )}
      </main>
    </div>
  );
}
