"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";

interface RankData {
  currentRank: string;
  currentIcon: string;
  currentRR: number;
  peakRank: string;
  peakIcon: string;
  peakRR: number;
  seasonLabel: string;
  createdAt: string | null;
  lastActivity: string | null;
  accountStatus: string | null;
  rankedRestriction: string | null;
}

interface WalletData {
  valorantPoints: number;
  radianitePoints: number;
  kingdomCredits: number;
  freeAgents: number;
  _raw_uuids?: string[];
}

interface InventoryItem {
  uuid: string;
  name: string;
  icon: string;
  type: string;
  large?: string;
  wide?: string;
  rarity?: string;
  rarityIcon?: string;
}

function SkeletonCard({ wide = false }: { wide?: boolean }) {
  return (
    <div
      className="rounded-lg overflow-hidden animate-pulse"
      style={{ background: "#1a2634", border: "1px solid #2a3a4a", height: wide ? 160 : 120 }}
    />
  );
}

function LoadingSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: "#0f1923" }}>
      <div className="text-center">
        <div className="w-12 h-12 border-2 rounded-full animate-spin mx-auto mb-4" style={{ borderColor: "#ff4655", borderTopColor: "transparent" }} />
        <p style={{ color: "#8b978f" }}>Đang tải dữ liệu...</p>
      </div>
    </div>
  );
}

function DashboardContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const accessToken = searchParams.get("accessToken") || "";
  const entitlementToken = searchParams.get("entitlementToken") || "";
  const puuid = searchParams.get("puuid") || "";
  const sessionId = searchParams.get("sessionId") || "";
  const gameName = searchParams.get("gameName") || "Player";
  const tagLine = searchParams.get("tagLine") || "";
  const region = searchParams.get("region") || "AP";
  const expiresAt = parseInt(searchParams.get("expiresAt") || "0", 10);

  const [activeTab, setActiveTab] = useState("overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [rank, setRank] = useState<RankData | null>(null);
  const [wallet, setWallet] = useState<WalletData | null>(null);
  const [skins, setSkins] = useState<InventoryItem[]>([]);
  const [agents, setAgents] = useState<InventoryItem[]>([]);
  const [cards, setCards] = useState<InventoryItem[]>([]);
  const [buddies, setBuddies] = useState<InventoryItem[]>([]);
  const [sprays, setSprays] = useState<InventoryItem[]>([]);
  const [shop, setShop] = useState<{ offers: InventoryItem[]; bundle: InventoryItem | null }>({ offers: [], bundle: null });
  const [version, setVersion] = useState("");
  const [skinSearch, setSkinSearch] = useState("");
  const [purchaseHistory, setPurchaseHistory] = useState<Array<{ amount: string; currency: string; date: string; method: string }>>([]);
  const [skinLevelCount, setSkinLevelCount] = useState(0);
  const [lastChecked, setLastChecked] = useState<string>("—");
  const [accountLevel, setAccountLevel] = useState<number>(0);
  const [emailVerified, setEmailVerified] = useState(false);
  const [phoneVerified, setPhoneVerified] = useState(false);
  const [country, setCountry] = useState<string>("—");

  // Redirect if missing params
  useEffect(() => {
    if (!accessToken && !sessionId) {
      router.replace("/");
    }
  }, [accessToken, sessionId, router]);

  // Fetch all data via API routes
  useEffect(() => {
    if (!accessToken || !entitlementToken || !puuid || !region) return;

    const fetchAll = async () => {
      setLoading(true);
      setError("");

      // First load version
      let ver = "shipping-14-10-19-17-40-14-bugfix";
      try {
        const r = await fetch("https://valorant-api.com/v1/version");
        const j = await r.json();
        if (j.data?.riotClientVersion) ver = j.data.riotClientVersion;
      } catch {
        // use default
      }
      setVersion(ver);

      // Auto-refresh token if sessionId is provided and token is within 5 min of expiry
      let currentAccessToken = accessToken;
      let currentEntitlementToken = entitlementToken;
      if (sessionId && expiresAt > 0 && expiresAt - Date.now() < 5 * 60 * 1000) {
        try {
          const refreshRes = await fetch("/api/auth/refresh", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ sessionId }),
          });
          if (refreshRes.ok) {
            const tokens = await refreshRes.json() as { accessToken: string; entitlementToken: string; expiresAt: number };
            currentAccessToken = tokens.accessToken;
            currentEntitlementToken = tokens.entitlementToken;
          }
        } catch {
          // proceed with existing token
        }
      }

      try {
        const [mmrRes, walletRes, skinsRes, agentsRes, cardsRes, buddiesRes, spraysRes, shopRes, accountXpRes, userInfoRes, purchaseRes] =
          await Promise.allSettled([
            fetch("/api/riot/mmr", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ accessToken: currentAccessToken, entitlementToken: currentEntitlementToken, version: ver, puuid, region, accountLevel }),
            }),
            fetch("/api/riot/wallet", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ accessToken: currentAccessToken, entitlementToken: currentEntitlementToken, version: ver, puuid, region }),
            }),
            fetch("/api/riot/inventory", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ accessToken: currentAccessToken, entitlementToken: currentEntitlementToken, version: ver, puuid, region, itemType: "skins" }),
            }),
            fetch("/api/riot/inventory", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ accessToken: currentAccessToken, entitlementToken: currentEntitlementToken, version: ver, puuid, region, itemType: "agents" }),
            }),
            fetch("/api/riot/inventory", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ accessToken: currentAccessToken, entitlementToken: currentEntitlementToken, version: ver, puuid, region, itemType: "cards" }),
            }),
            fetch("/api/riot/inventory", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ accessToken: currentAccessToken, entitlementToken: currentEntitlementToken, version: ver, puuid, region, itemType: "buddies" }),
            }),
            fetch("/api/riot/inventory", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ accessToken: currentAccessToken, entitlementToken: currentEntitlementToken, version: ver, puuid, region, itemType: "sprays" }),
            }),
            fetch("/api/riot/shop", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ accessToken: currentAccessToken, entitlementToken: currentEntitlementToken, version: ver, puuid, region }),
            }),
            fetch("/api/riot/accountxp", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ accessToken: currentAccessToken, entitlementToken: currentEntitlementToken, version: ver, puuid, region }),
            }),
            fetch("/api/riot/userinfo", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ accessToken: currentAccessToken }),
            }),
            fetch("/api/riot/purchase", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ accessToken: currentAccessToken, entitlementToken: currentEntitlementToken, version: ver, puuid, region }),
            }),
          ]);

        // MMR
        if (mmrRes.status === "fulfilled" && mmrRes.value.ok) {
          const data = await mmrRes.value.json();
          console.log("MMR response:", JSON.stringify(data));
          setRank(data);
        } else if (mmrRes.status === "rejected") {
          console.error("MMR rejected:", mmrRes.reason);
        } else if (mmrRes.status === "fulfilled" && !mmrRes.value.ok) {
          const text = await mmrRes.value.text();
          console.error("MMR error response:", text);
        }

        // Wallet
        if (walletRes.status === "fulfilled" && walletRes.value.ok) {
          const data = await walletRes.value.json();
          console.log("Wallet response:", data);
          setWallet(data);
        } else if (walletRes.status === "rejected") {
          console.error("Wallet rejected:", walletRes.reason);
        } else if (walletRes.status === "fulfilled" && !walletRes.value.ok) {
          const text = await walletRes.value.text();
          console.error("Wallet error response:", text);
        }

        // Skin level count (must read before parseInventory consumes the stream)
        if (skinsRes.status === "fulfilled" && skinsRes.value.ok) {
          const skinsData = await skinsRes.value.clone().json();
          setSkins(skinsData.items || []);
          setSkinLevelCount(skinsData.levelCount ?? 0);
        }

        // Other inventory items
        const parseInventory = async (res: PromiseSettledResult<Response>, setter: (v: InventoryItem[]) => void, name: string) => {
          if (res.status === "fulfilled" && res.value.ok) {
            const data = await res.value.json();
            console.log(`${name} response:`, data);
            setter(data.items || []);
          } else if (res.status === "fulfilled" && !res.value.ok) {
            const text = await res.value.text();
            console.error(`${name} error:`, text);
          } else if (res.status === "rejected") {
            console.error(`${name} rejected:`, res.reason);
          }
        };

        await Promise.all([
          parseInventory(agentsRes, setAgents, "Agents"),
          parseInventory(cardsRes, setCards, "Cards"),
          parseInventory(buddiesRes, setBuddies, "Buddies"),
          parseInventory(spraysRes, setSprays, "Sprays"),
        ]);

        // Shop
        if (shopRes.status === "fulfilled" && shopRes.value.ok) {
          const data = await shopRes.value.json();
          console.log("Shop response:", data);
          setShop({ offers: data.offers || [], bundle: data.bundle || null });
        } else if (shopRes.status === "rejected") {
          console.error("Shop rejected:", shopRes.reason);
        } else if (shopRes.status === "fulfilled" && !shopRes.value.ok) {
          const text = await shopRes.value.text();
          console.error("Shop error response:", text);
        }

        // Account XP
        if (accountXpRes.status === "fulfilled" && accountXpRes.value.ok) {
          const data = await accountXpRes.value.clone().json();
          console.log("Account XP response:", JSON.stringify(data));
          // Extract level from Progress — handle both nested and flat structures
          const progress = data?.Progress;
          console.log("Account XP Progress:", JSON.stringify(progress));
          const level =
            typeof progress?.Level === "number"
              ? progress.Level
              : typeof data?.Level === "number"
              ? data.Level
              : typeof data?.accountLevel === "number"
              ? data.accountLevel
              : 0;
          console.log("Account XP level extracted:", level, "from data keys:", Object.keys(data));
          setAccountLevel(level);
        }

        // User info
        if (userInfoRes.status === "fulfilled" && userInfoRes.value.ok) {
          const data = await userInfoRes.value.json();
          setEmailVerified(data.email_verified ?? false);
          setPhoneVerified(data.phone_number_verified ?? false);
          setCountry(typeof data.country === "string" ? data.country.toUpperCase() : "—");
        }

        // Purchase history
        if (purchaseRes.status === "fulfilled" && purchaseRes.value.ok) {
          const data = await purchaseRes.value.json();
          setPurchaseHistory(data.history ?? []);
        }

        setLastChecked(new Date().toLocaleString("vi-VN"));
        setLoading(false);
      } catch (e) {
        console.error("fetchAll error:", e);
        setError("Lỗi kết nối. Token có thể đã hết hạn.");
        setLoading(false);
      }
    };

    fetchAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken, entitlementToken, sessionId, expiresAt, puuid, region]);

  // Countdown
  const [countdown, setCountdown] = useState("");
  useEffect(() => {
    if (!expiresAt) return;
    const tick = () => {
      const diff = expiresAt - Date.now();
      if (diff <= 0) { setCountdown("Hết hạn"); return; }
      const m = Math.floor(diff / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      setCountdown(`${m}m ${s}s`);
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [expiresAt]);

  const filteredSkins = skins.filter((s) =>
    !skinSearch || s.name.toLowerCase().includes(skinSearch.toLowerCase())
  );

  const TABS = [
    { key: "overview", label: "Info" },
    { key: "skins", label: `Skins (${skins.length})` },
    { key: "agents", label: `Agents (${agents.length})` },
    { key: "shop", label: "Shop" },
    { key: "cards", label: `Playercards (${cards.length})` },
    { key: "buddies", label: `Buddies (${buddies.length})` },
    { key: "sprays", label: `Sprays (${sprays.length})` },
    { key: "purchase", label: purchaseHistory.length ? `Purchase History (${purchaseHistory.length})` : "Purchase History" },
  ];

  return (
    <div className="min-h-screen" style={{ background: "#0f1923", color: "#ece8e1", fontFamily: "'Segoe UI', system-ui, sans-serif" }}>
      {/* Header */}
      <header style={{ borderBottom: "2px solid #ff4655" }}>
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
              <circle cx="16" cy="16" r="16" fill="#ff4655"/>
              <polygon points="16,6 22,12 16,18 10,12" fill="white"/>
              <rect x="14" y="18" width="4" height="8" fill="white"/>
            </svg>
            <span className="font-bold text-white">{gameName}#{tagLine}</span>
          </div>
          <div className="flex items-center gap-3">
            {countdown && (
              <span className="text-xs px-3 py-1 rounded" style={{ background: "#1a2634", border: "1px solid #2a3a4a", color: "#8b978f" }}>
                Token: {countdown}
              </span>
            )}
            <a href="/" className="text-xs px-3 py-1.5 rounded border text-gray-400 hover:text-white" style={{ borderColor: "#2a3a4a" }}>
              Đổi token
            </a>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6">
        {error && (
          <div className="mb-6 p-4 rounded-lg" style={{ background: "rgba(183,28,28,0.3)", border: "1px solid #b71c1c", color: "#ff5252" }}>
            {error}
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-2 mb-6 flex-wrap" style={{ borderBottom: "2px solid #2a3a4a", paddingBottom: "6px" }}>
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className="px-4 py-2 rounded text-sm font-medium transition-all cursor-pointer"
              style={{
                background: activeTab === tab.key ? "#ff4655" : "#1a2634",
                color: activeTab === tab.key ? "#fff" : "#8b978f",
                border: `1px solid ${activeTab === tab.key ? "#ff4655" : "#2a3a4a"}`,
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* ============ OVERVIEW ============ */}
        {activeTab === "overview" && (
          <div className="space-y-4">
            {/* Header bar */}
            <div style={{ textAlign: "center", padding: "20px 0", borderBottom: "2px solid #ff4655", marginBottom: 20 }}>
              <h1 style={{ fontSize: "2em", color: "#ff4655", letterSpacing: "1.5px", marginBottom: 6 }}>{gameName}#{tagLine}</h1>
              <p style={{ color: "#8b978f", fontSize: "0.9em" }}>Last checked: {lastChecked}</p>
            </div>

            {/* Status Banner */}
            {(() => {
              const status = rank?.accountStatus ?? "Active";
              if (status === "Active") return null;
              const isPermBan = status.startsWith("BANNED") || status.startsWith("PERMANENT");
              const isSuspended = status.toLowerCase().includes("suspend") || status.includes("Khoa") || status.includes("khoa") || status.includes("Suspended");
              const isLocked = status.includes("LOCKED") || status.includes("FLAGGED") || status.includes("Locked") || status.includes("Flagged");
              const bg = isPermBan ? "rgba(183,28,28,0.25)" : isSuspended ? "rgba(255,152,0,0.2)" : "rgba(255,193,7,0.15)";
              const border = isPermBan ? "#b71c1c" : isSuspended ? "#ff6d00" : "#f9a825";
              const icon = isPermBan ? "🚫" : isSuspended ? "⏸" : "🔒";
              const label = isPermBan ? "TAI KHOAN BI CAM VINH VIEN" : isSuspended ? "TAI KHOAN BI KHOA TAM THOI" : isLocked ? "RANK BI KHOA" : "TAI KHOAN CO VAN DE";
              return (
                <div style={{ padding: "14px 20px", borderRadius: 10, background: bg, border: `1px solid ${border}`, marginBottom: 16 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: "1.4em" }}>{icon}</span>
                    <span style={{ fontWeight: 700, fontSize: "1.1em", color: "#fff", letterSpacing: "0.5px" }}>{label}</span>
                  </div>
                </div>
              );
            })()}

            {/* 2-column info layout */}
            <div className="rounded-xl overflow-hidden" style={{ background: "#1a2634", border: "1px solid #2a3a4a" }}>
              <div style={{ display: "flex", gap: 24, alignItems: "flex-start", padding: 16 }}>
                {/* Left: Player Card artwork */}
                <div style={{ flex: "0 0 220px" }}>
                  {cards[0]?.large ? (
                    <img
                      src={cards[0].large}
                      alt="Player Card"
                      style={{ width: "100%", borderRadius: 10, border: "2px solid #2a3a4a", display: "block" }}
                      onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                    />
                  ) : cards[0]?.wide ? (
                    <img
                      src={cards[0].wide}
                      alt="Player Card"
                      style={{ width: "100%", borderRadius: 10, border: "2px solid #2a3a4a", display: "block" }}
                      onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                    />
                  ) : cards[0]?.icon ? (
                    <img
                      src={cards[0].icon}
                      alt="Player Card"
                      style={{ width: "100%", borderRadius: 10, border: "2px solid #2a3a4a", display: "block" }}
                      onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                    />
                  ) : null}
                </div>

                {/* Right: Info */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  {/* Header + currency inline */}
                  <div style={{ marginBottom: 12, paddingBottom: 10, borderBottom: "1px solid #2a3a4a" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                      <span style={{ color: "#8b978f", fontSize: "0.85em" }}>Username: <strong style={{ color: "#ece8e1" }}>{gameName}</strong></span>
                      {/* Currency bar */}
                      <div style={{ display: "flex", gap: 6, marginLeft: "auto", flexWrap: "wrap" }}>
                        {[
                          { label: "Valorant Points", short: "VP", value: wallet?.valorantPoints, color: "#ff4655", icon: "https://media.valorant-api.com/currencies/85ad13f7-3d1b-5128-9eb2-7cd8ee0b5741/displayicon.png" },
                          { label: "Radianite Points", short: "RP", value: wallet?.radianitePoints, color: "#4caf50", icon: "https://media.valorant-api.com/currencies/e59aa87c-4cbf-517a-5983-6e81511be9b7/displayicon.png" },
                          { label: "Kingdom Credits", short: "KC", value: wallet?.kingdomCredits, color: "#f5a623", icon: "https://media.valorant-api.com/currencies/85ca954a-41f2-ce94-9b45-8ca3dd39a00d/displayicon.png" },
                          { label: "Free Agents", short: "FA", value: wallet?.freeAgents, color: "#ece8e1", icon: "https://media.valorant-api.com/currencies/f08d4ae3-939c-4576-ab26-09ce1f23bb37/displayicon.png" },
                        ].map(({ short, value, color, icon }) => (
                          <div key={short} style={{ display: "flex", alignItems: "center", gap: 4, background: "#0d1520", border: "1px solid #2a3a4a", borderRadius: 6, padding: "4px 10px" }}>
                            <img src={icon} alt={short} style={{ width: 16, height: 16 }} onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />
                            <span style={{ fontWeight: 700, fontSize: "0.85em", color }}>{value != null ? (typeof value === "number" ? value.toLocaleString() : value) : "—"}</span>
                            <span style={{ color: "#8b978f", fontSize: "0.72em" }}>{short}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Info rows */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 20px" }}>
                    {[
                      { label: "PUUID", value: puuid, wide: true },
                      { label: "Level", value: accountLevel > 0 ? accountLevel : "—" },
                      { label: "Region", value: region.toUpperCase() },
                      { label: "Country", value: country },
                      { label: "Email Verified", value: emailVerified ? "Yes" : "No", badge: true, badgeColor: emailVerified ? "#4caf50" : "#ff5252" },
                      { label: "Phone Verified", value: phoneVerified ? "Yes" : "No", badge: true, badgeColor: phoneVerified ? "#4caf50" : "#ff5252" },
                      { label: "Account Created", value: rank?.createdAt ?? "—" },
                      { label: "Status", value: rank?.accountStatus ?? "Active", badge: true,
                        badgeColor: (() => {
                          const s = rank?.accountStatus ?? "Active";
                          if (s === "Active") return "#4caf50";
                          if (s.startsWith("BANNED") || s.startsWith("PERMANENT")) return "#ff5252";
                          if (s.toLowerCase().includes("suspend") || s.includes("Khoa") || s.includes("khoa")) return "#ff9800";
                          if (s.includes("LOCKED") || s.includes("FLAGGED") || s.includes("Locked") || s.includes("Flagged")) return "#ffc107";
                          return "#ff5252";
                        })(),
                        badgeBg: (() => {
                          const s = rank?.accountStatus ?? "Active";
                          if (s === "Active") return "#1b5e20";
                          if (s.startsWith("BANNED") || s.startsWith("PERMANENT")) return "#3e1010";
                          if (s.toLowerCase().includes("suspend") || s.includes("Khoa") || s.includes("khoa")) return "#3e2200";
                          if (s.includes("LOCKED") || s.includes("FLAGGED") || s.includes("Locked") || s.includes("Flagged")) return "#3e3500";
                          return "#2a3a4a";
                        })(),
                        wide: true },
                      { label: "Ranked Restriction", value: rank?.rankedRestriction ?? "None", badge: true,
                        badgeColor: rank?.rankedRestriction ? "#ff9800" : "#4caf50",
                        badgeBg: rank?.rankedRestriction ? "#3e2200" : "#1b5e20",
                        wide: true },
                      { label: "Last Activity", value: rank?.lastActivity ?? "—", wide: true },
                      { label: "Season", value: rank?.seasonLabel ?? "—" },
                    ].map(({ label, value, wide, badge, badgeColor, badgeBg }) => (
                      <div key={label} style={{ display: "flex", padding: "7px 0", borderBottom: "1px solid rgba(42,58,74,0.3)", alignItems: "center", gridColumn: wide ? "1 / -1" : undefined }}>
                        <span style={{ color: "#8b978f", fontSize: "0.78em", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "2px", minWidth: 140, flexShrink: 0 }}>{label}</span>
                        {badge ? (
                          <span style={{ display: "inline-block", padding: "2px 8px", borderRadius: 4, fontSize: "0.8em", fontWeight: 600, background: badgeBg ?? "#2a3a4a", color: badgeColor }}>{value}</span>
                        ) : (
                          <span style={{ fontWeight: 600, fontSize: "0.92em", color: "#ece8e1", wordBreak: "break-all" }}>{value}</span>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Rank Progression */}
                  <div style={{ marginTop: 16, paddingTop: 14, borderTop: "1px solid #2a3a4a" }}>
                    <p style={{ color: "#8b978f", fontSize: "0.78em", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 10 }}>Rank Progression</p>
                    {loading ? (
                      <div style={{ display: "flex", gap: 12 }}>
                        {[1, 2, 3].map((i) => <SkeletonCard key={i} />)}
                      </div>
                    ) : (
                      <div style={{ display: "flex", gap: 12 }}>
                        {[
                          { label: "Current Rank", icon: rank?.currentIcon, name: rank?.currentRank, rr: rank?.currentRR },
                          { label: "Peak Rank", icon: rank?.peakIcon, name: rank?.peakRank, rr: rank?.peakRR },
                          { label: "Previous Season", icon: rank?.currentIcon, name: rank?.seasonLabel ?? "—", rr: null as number | null },
                        ].map(({ label, icon, name, rr }) => (
                          <div key={label} style={{ flex: 1, background: "#0d1520", border: "1px solid #2a3a4a", borderRadius: 10, padding: 14, textAlign: "center" }}>
                            <p style={{ color: "#8b978f", fontSize: "0.72em", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 8 }}>{label}</p>
                            {icon && <img src={icon} alt={name ?? ""} style={{ width: 64, height: 64, margin: "0 auto 8px", display: "block" }} onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }} />}
                            <p style={{ fontWeight: 700, fontSize: "1em", marginBottom: 2 }}>{name ?? "—"}</p>
                            {rr != null && rr > 0 && <p style={{ color: "#8b978f", fontSize: "0.82em" }}>{rr} RR</p>}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Quick stats */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10 }}>
              {[
                { label: "Skins", value: skins.length },
                { label: "Agents", value: agents.length },
                { label: "Cards", value: cards.length },
                { label: "Buddies", value: buddies.length },
                { label: "Sprays", value: sprays.length },
              ].map(({ label, value }) => (
                <div key={label} style={{ background: "#1a2634", border: "1px solid #2a3a4a", borderRadius: 8, padding: "12px 8px", textAlign: "center" }}>
                  <p style={{ fontSize: "1.4em", fontWeight: 700, color: "#ff4655" }}>{value}</p>
                  <p style={{ fontSize: "0.72em", color: "#8b978f", textTransform: "uppercase", letterSpacing: "0.5px" }}>{label}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ============ SKINS ============ */}
        {activeTab === "skins" && (
          <div>
            {/* Stats bar */}
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
              <span style={{ color: "#8b978f", fontSize: "0.85em" }}>
                Skins: <strong style={{ color: "#ece8e1" }}>{skins.length}</strong>
                {skinLevelCount > 0 && (
                  <> | Skin Levels: <strong style={{ color: "#ece8e1" }}>{skinLevelCount}</strong></>
                )}
              </span>
            </div>

            {/* Filter bar */}
            <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap", alignItems: "center" }}>
              <input
                type="text"
                placeholder="Tìm kiếm skin..."
                value={skinSearch}
                onChange={(e) => setSkinSearch(e.target.value)}
                style={{ flex: 1, minWidth: 200, background: "#1a2634", border: "1px solid #2a3a4a", color: "#ece8e1", outline: "none", padding: "6px 12px", borderRadius: 6, fontSize: "0.85em" }}
              />
            </div>

            {loading ? (
              <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3">
                {Array.from({ length: 12 }).map((_, i) => <SkeletonCard key={i} />)}
              </div>
            ) : filteredSkins.length > 0 ? (
              <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-3">
                {filteredSkins.map((skin) => (
                  <div key={skin.uuid} className="rounded-lg overflow-hidden transition-transform hover:-translate-y-1 relative" style={{ background: "#1a2634", border: "1px solid #2a3a4a" }}>
                    {/* Rarity badge */}
                    {skin.rarityIcon ? (
                      <img
                        src={skin.rarityIcon}
                        alt={skin.rarity ?? ""}
                        title={skin.rarity ?? ""}
                        style={{ position: "absolute", top: 4, left: 4, width: 20, height: 20, zIndex: 2, borderRadius: 4 }}
                        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                      />
                    ) : null}
                    <div className="w-full h-24 flex items-center justify-center p-2" style={{ background: "#0d1520" }}>
                      {skin.icon ? (
                        <img src={skin.icon} alt={skin.name} className="max-w-full max-h-full object-contain" loading="lazy" />
                      ) : (
                        <div className="w-8 h-8 rounded bg-[#1a2634]" />
                      )}
                    </div>
                    <div className="px-2 py-2 text-center text-xs font-medium" style={{ borderTop: "1px solid #2a3a4a" }}>
                      {skin.name}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-center py-12 text-gray-500">Không tìm thấy skin.</p>
            )}
          </div>
        )}

        {/* ============ AGENTS ============ */}
        {activeTab === "agents" && (
          loading ? (
            <div className="grid grid-cols-5 sm:grid-cols-7 md:grid-cols-10 gap-2">
              {Array.from({ length: 10 }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
          ) : agents.length > 0 ? (
            <div className="grid grid-cols-5 sm:grid-cols-7 md:grid-cols-10 gap-2">
              {agents.map((a) => (
                <div key={a.uuid} className="rounded-lg overflow-hidden text-center transition-transform hover:-translate-y-1" style={{ background: "#1a2634", border: "1px solid #2a3a4a" }}>
                  <div className="w-full h-20 flex items-center justify-center p-1" style={{ background: "#0d1520" }}>
                    {a.icon ? <img src={a.icon} alt={a.name} className="max-h-full object-contain" loading="lazy" /> : <div className="w-8 h-8 bg-[#1a2634] rounded" />}
                  </div>
                  <div className="px-1 py-1.5 text-[10px] font-bold" style={{ borderTop: "1px solid #2a3a4a" }}>{a.name}</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center py-12 text-gray-500">Không có agent.</p>
          )
        )}

        {/* ============ SHOP ============ */}
        {activeTab === "shop" && (
          loading ? (
            <div className="grid grid-cols-4 gap-3">
              {Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
          ) : (
            <div className="space-y-6">
              <div>
                <h3 className="text-base font-bold mb-3" style={{ color: "#ff4655" }}>Daily Offers</h3>
                {shop.offers.length > 0 ? (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    {shop.offers.map((item) => (
                      <div key={item.uuid} className="rounded-lg overflow-hidden" style={{ background: "#1a2634", border: "1px solid #2a3a4a" }}>
                        <div className="w-full h-24 flex items-center justify-center p-2" style={{ background: "#0d1520" }}>
                          {item.icon ? <img src={item.icon} alt={item.name} className="max-w-full max-h-full object-contain" /> : <div className="w-8 h-8 bg-[#1a2634] rounded" />}
                        </div>
                        <div className="px-2 py-2 text-center text-xs" style={{ borderTop: "1px solid #2a3a4a" }}>{item.name}</div>
                      </div>
                    ))}
                  </div>
                ) : <p className="text-gray-500 text-sm italic">Không có daily offers.</p>}
              </div>
            </div>
          )
        )}

        {/* ============ CARDS ============ */}
        {activeTab === "cards" && (
          loading ? (
            <div className="grid grid-cols-7 md:grid-cols-10 gap-2">
              {Array.from({ length: 10 }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
          ) : cards.length > 0 ? (
            <div className="grid grid-cols-7 md:grid-cols-10 gap-2">
              {cards.map((c) => (
                <div key={c.uuid} className="rounded-lg overflow-hidden text-center" style={{ background: "#1a2634", border: "1px solid #2a3a4a" }}>
                  <div className="w-full h-14" style={{ background: "#0d1520" }}>
                    {c.icon ? <img src={c.icon} alt={c.name} className="w-full h-full object-cover" loading="lazy" /> : null}
                  </div>
                  <div className="px-1 py-1 text-[10px] font-medium" style={{ borderTop: "1px solid #2a3a4a" }}>{c.name}</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center py-12 text-gray-500">Không có card.</p>
          )
        )}

        {/* ============ BUDDIES ============ */}
        {activeTab === "buddies" && (
          loading ? (
            <div className="grid grid-cols-8 md:grid-cols-10 gap-2">
              {Array.from({ length: 10 }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
          ) : buddies.length > 0 ? (
            <div className="grid grid-cols-8 md:grid-cols-10 gap-2">
              {buddies.map((b) => (
                <div key={b.uuid} className="rounded-lg overflow-hidden text-center" style={{ background: "#1a2634", border: "1px solid #2a3a4a" }}>
                  <div className="w-full h-14 flex items-center justify-center p-1" style={{ background: "#0d1520" }}>
                    {b.icon ? <img src={b.icon} alt={b.name} className="max-w-full max-h-full object-contain" loading="lazy" /> : <div className="w-6 h-6 bg-[#1a2634] rounded" />}
                  </div>
                  <div className="px-1 py-1 text-[10px] font-medium" style={{ borderTop: "1px solid #2a3a4a" }}>{b.name}</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center py-12 text-gray-500">Không có buddy.</p>
          )
        )}

        {/* ============ SPRAYS ============ */}
        {activeTab === "sprays" && (
          loading ? (
            <div className="grid grid-cols-8 md:grid-cols-10 gap-2">
              {Array.from({ length: 10 }).map((_, i) => <SkeletonCard key={i} />)}
            </div>
          ) : sprays.length > 0 ? (
            <div className="grid grid-cols-8 md:grid-cols-10 gap-2">
              {sprays.map((s) => (
                <div key={s.uuid} className="rounded-lg overflow-hidden text-center" style={{ background: "#1a2634", border: "1px solid #2a3a4a" }}>
                  <div className="w-full h-14 flex items-center justify-center p-1" style={{ background: "#0d1520" }}>
                    {s.icon ? <img src={s.icon} alt={s.name} className="max-w-full max-h-full object-contain" loading="lazy" /> : <div className="w-6 h-6 bg-[#1a2634] rounded" />}
                  </div>
                  <div className="px-1 py-1 text-[10px] font-medium" style={{ borderTop: "1px solid #2a3a4a" }}>{s.name}</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-center py-12 text-gray-500">Không có spray.</p>
          )
        )}

        {/* ============ PURCHASE HISTORY ============ */}
        {activeTab === "purchase" && (
          <div>
            {purchaseHistory.length > 0 ? (
              <table style={{ width: "100%", borderCollapse: "separate", borderSpacing: "0 4px" }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", color: "#8b978f", fontSize: "0.75em", textTransform: "uppercase", padding: "6px 10px", letterSpacing: "0.5px" }}>#</th>
                    <th style={{ textAlign: "left", color: "#8b978f", fontSize: "0.75em", textTransform: "uppercase", padding: "6px 10px", letterSpacing: "0.5px" }}>Amount</th>
                    <th style={{ textAlign: "left", color: "#8b978f", fontSize: "0.75em", textTransform: "uppercase", padding: "6px 10px", letterSpacing: "0.5px" }}>Payment Method</th>
                    <th style={{ textAlign: "left", color: "#8b978f", fontSize: "0.75em", textTransform: "uppercase", padding: "6px 10px", letterSpacing: "0.5px" }}>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {purchaseHistory.map((tx, i) => (
                    <tr key={i}>
                      <td style={{ background: "#1a2634", padding: "8px 10px", borderRadius: "6px 0 0 6px", color: "#ff4655", fontWeight: 700, width: 40, textAlign: "center" }}>{i + 1}</td>
                      <td style={{ background: "#1a2634", padding: "8px 10px", color: "#ece8e1", fontWeight: 600 }}>{tx.amount} {tx.currency}</td>
                      <td style={{ background: "#1a2634", padding: "8px 10px", color: "#8b978f", fontSize: "0.82em" }}>{tx.method}</td>
                      <td style={{ background: "#1a2634", padding: "8px 10px", borderRadius: "0 6px 6px 0", color: "#ece8e1" }}>{tx.date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p style={{ color: "#8b978f", fontStyle: "italic", padding: "12px 0" }}>Không có lịch sử giao dịch.</p>
            )}
          </div>
        )}

        {/* Footer */}
        <div style={{ textAlign: "center", color: "#8b978f", fontSize: "0.8em", marginTop: 30, paddingTop: 15, borderTop: "1px solid #2a3a4a" }}>
          Valorant Account Checker
        </div>
      </main>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<LoadingSpinner />}>
      <DashboardContent />
    </Suspense>
  );
}
