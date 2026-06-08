import { NextRequest, NextResponse } from "next/server";
import {
  fetchEntitlementToken,
  fetchRank,
  fetchWallet,
  fetchUserInfo,
  fetchAccountXp,
  fetchRankedRestrictions,
  fetchInventory,
  fetchVersion,
} from "@/lib/riotApi";
import { getSession, updateSession } from "@/lib/authStore";
import type { Region } from "@/lib/types";

/** Refreshes a session's access + entitlement tokens, updates the session file, returns null on failure. */
async function refreshSessionTokens(sessionId: string): Promise<{
  accessToken: string;
  entitlementToken: string;
  expiresAt: number;
} | null> {
  const session = getSession(sessionId);
  if (!session) return null;

  try {
    const tokenRes = await fetch("https://auth.riotgames.com/token", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "refresh_token",
        refresh_token: session.refreshToken,
        client_id: "riot-client",
      }),
    });

    if (!tokenRes.ok) return null;

    const tokenData = await tokenRes.json() as {
      access_token: string;
      refresh_token?: string;
      expires_in: number;
    };

    const entitlementToken = await fetchEntitlementToken(tokenData.access_token);
    const expiresAt = Date.now() + (tokenData.expires_in ?? 3600) * 1000;

    // Persist new tokens so the session file stays current for future requests
    updateSession(sessionId, {
      accessToken: tokenData.access_token,
      refreshToken: tokenData.refresh_token ?? session.refreshToken,
      expiresAt,
      entitlementToken,
    });

    return { accessToken: tokenData.access_token, entitlementToken, expiresAt };
  } catch {
    return null;
  }
}

/** Fetches all account data for a given token set. */
async function fetchAccountData(
  accessToken: string,
  entitlementToken: string,
  region: string,
  fallbackGameName?: string,
  fallbackTagLine?: string
): Promise<Record<string, unknown>> {
  let ver = "shipping-14-10-19-17-40-14-bugfix";
  try {
    ver = await fetchVersion();
  } catch { /* use default */ }

  const userInfo = await fetchUserInfo(accessToken) as Record<string, unknown> | null;
  const puuid: string = (userInfo?.sub as string) ?? "";

  const [mmrRes, walletRes, accountXpData, restrictionsRes] = await Promise.allSettled([
    fetchRank(accessToken, entitlementToken, ver, puuid, region as Region),
    fetchWallet(accessToken, entitlementToken, ver, puuid, region as Region),
    fetchAccountXp(accessToken, entitlementToken, ver, puuid, region as Region),
    fetchRankedRestrictions(accessToken, entitlementToken, ver, puuid, region as Region),
  ]);

  const mmr = mmrRes.status === "fulfilled" && mmrRes.value ? mmrRes.value : null;
  const wallet = walletRes.status === "fulfilled" && walletRes.value ? walletRes.value : null;
  const accountXp = accountXpData.status === "fulfilled" && accountXpData.value
    ? accountXpData.value as Record<string, unknown> : null;
  const restrictionsData = restrictionsRes.status === "fulfilled" && restrictionsRes.value
    ? restrictionsRes.value as Record<string, unknown> : null;

  // Skin level count
  let levelCount = 0;
  try {
    const inv = await fetchInventory(accessToken, entitlementToken, ver, puuid, region as Region, "00082d4f-e8b0-4ce9-ba7e-40aae1757e40");
    levelCount = inv?.Entitlements?.length ?? 0;
  } catch { /* ignore */ }

  const tier = mmr?.LatestCompetitiveUpdate?.TierAfterUpdate ?? 0;
  const rr = mmr?.LatestCompetitiveUpdate?.RankedRatingAfterUpdate ?? 0;
  const ui = userInfo;
  const createdAt = ui?.acct && typeof ui.acct === "object"
    ? new Date((ui.acct as Record<string, unknown>).created_at as string).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" })
    : null;

  let accountStatus = "Active";
  const banInfo = ui?.ban ?? null;
  if (banInfo && typeof banInfo === "object") {
    const flag = (banInfo as Record<string, unknown>).flag as string | undefined;
    if (flag) accountStatus = `BANNED: ${flag}`;
  }

  let rankedRestriction: string | null = null;
  if (restrictionsData) {
    const raw = restrictionsData.restrictions as Array<Record<string, unknown>> | undefined;
    if (Array.isArray(raw) && raw.length > 0) {
      const types = raw.map((r) => (r.type as string) || (r.reason as string)).filter(Boolean);
      rankedRestriction = types.join("; ") || null;
    } else if (restrictionsData.errorCode) {
      rankedRestriction = `[${restrictionsData.errorCode}] ${restrictionsData.errorMsg ?? ""}`;
    }
  }

  return {
    success: true,
    region,
    puuid,
    gameName: fallbackGameName ?? (ui?.game_name as string) ?? "Unknown",
    tagLine: fallbackTagLine ?? (ui?.tag_line as string) ?? "Unknown",
    level: accountXp?.Progress?.Level ?? accountXp?.level ?? 0,
    currentRank: tier,
    currentRR: rr,
    valorantPoints: wallet?.valorantPoints ?? 0,
    radianitePoints: wallet?.radianitePoints ?? 0,
    kingdomCredits: wallet?.kingdomCredits ?? 0,
    freeAgents: wallet?.freeAgents ?? 0,
    levelCount,
    createdAt,
    accountStatus,
    country: typeof ui?.country === "string" ? ui.country : null,
    emailVerified: ui?.email_verified ?? false,
    phoneVerified: ui?.phone_number_verified ?? false,
    rankedRestriction,
  };
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { accounts, sessionIds } = body as {
      accounts?: Array<{ accessToken: string; region: string; gameName?: string; tagLine?: string }>;
      sessionIds?: string[];
    };

    const results: Array<Record<string, unknown>> = [];

    // ─── MODE 1: Saved Sessions ───────────────────────────────────────────────
    if (Array.isArray(sessionIds) && sessionIds.length > 0) {
      const settled = await Promise.allSettled(
        sessionIds.map(async (sessionId) => {
          const session = getSession(sessionId);

          if (!session) {
            return {
              success: false,
              error: "Session not found or expired",
              region: "—",
              gameName: "—",
              tagLine: "—",
            };
          }

          // Determine if token needs refresh (within 5 min of expiry)
          const needsRefresh = !session.expiresAt || session.expiresAt - Date.now() < 5 * 60 * 1000;
          let accessToken: string;
          let entitlementToken: string;

          if (needsRefresh) {
            const refreshed = await refreshSessionTokens(sessionId);
            if (!refreshed) {
              return {
                success: false,
                error: "Token refresh failed — please re-login at /auth",
                region: session.region,
                gameName: session.gameName,
                tagLine: session.tagLine,
              };
            }
            accessToken = refreshed.accessToken;
            entitlementToken = refreshed.entitlementToken;
          } else {
            accessToken = session.accessToken;
            entitlementToken = session.entitlementToken;
          }

          return fetchAccountData(accessToken, entitlementToken, session.region, session.gameName, session.tagLine);
        })
      );

      for (const r of settled) {
        if (r.status === "fulfilled") {
          results.push(r.value);
        } else {
          results.push({ success: false, error: r.reason?.message ?? "Unknown error", region: "—", gameName: "—", tagLine: "—" });
        }
      }

      return NextResponse.json({ results });
    }

    // ─── MODE 2: Direct Access Tokens (existing behavior) ────────────────────
    if (!Array.isArray(accounts)) {
      return NextResponse.json({ error: "accounts must be an array" }, { status: 400 });
    }

    const settled = await Promise.allSettled(
      accounts.map(async (account) => {
        const { accessToken, region } = account;

        try {
          const entitlementToken = await fetchEntitlementToken(accessToken);
          return fetchAccountData(accessToken, entitlementToken, region, account.gameName, account.tagLine);
        } catch (e: unknown) {
          const msg = e instanceof Error ? e.message : "Unknown error";
          return {
            success: false,
            error: msg,
            region,
            gameName: account.gameName ?? "Unknown",
            tagLine: account.tagLine ?? "Unknown",
          };
        }
      })
    );

    for (const r of settled) {
      if (r.status === "fulfilled") {
        results.push(r.value);
      } else {
        results.push({ success: false, error: r.reason?.message ?? "Unknown error", region: "—", gameName: "—", tagLine: "—" });
      }
    }

    return NextResponse.json({ results });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
