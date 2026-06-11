import { NextRequest, NextResponse } from "next/server";
import { fetchRank, fetchRankTiers, fetchUserInfo, fetchRankedRestrictions } from "@/lib/riotApi";
import type { Region } from "@/lib/types";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { accessToken, entitlementToken, version, puuid, region, accountLevel: clientAccountLevel } = body;
    if (!accessToken || !entitlementToken || !puuid || !region) {
      return NextResponse.json({ error: "Missing required fields" }, { status: 400 });
    }

    const [mmrData, rankTiers, userInfo, restrictionsData] = await Promise.all([
      fetchRank(accessToken, entitlementToken, version, puuid, region as Region),
      fetchRankTiers(),
      fetchUserInfo(accessToken),
      fetchRankedRestrictions(accessToken, entitlementToken, version, puuid, region as Region),
    ]);

    // Account level — prefer client-passed value, fallback to mmr endpoint data
    const accountLevelFromMMR = mmrData?.AccountLevel ?? 0;
    const accountLevel = clientAccountLevel > 0 ? clientAccountLevel : accountLevelFromMMR;

    // Account creation + last activity + status from userinfo
    const createdAt = userInfo?.acct?.created_at
      ? new Date(userInfo.acct.created_at).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" })
      : null;

    // Last competitive activity — check main endpoint first, then competitive history
    let lastActivity: string | null = null;
    if (mmrData?.LatestCompetitiveUpdate?.MatchStartTime) {
      lastActivity = new Date(mmrData.LatestCompetitiveUpdate.MatchStartTime).toLocaleString("vi-VN", {
        day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
      });
    } else if (mmrData?.__hasCompetitiveHistory__) {
      // Use most recent match from competitive history
      const hist = mmrData.CompetitiveStats;
      if (Array.isArray(hist?.Matches) && hist.Matches.length > 0) {
        const latest = hist.Matches[0];
        if (latest.matchStartTime) {
          lastActivity = new Date(latest.matchStartTime as string).toLocaleString("vi-VN", {
            day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
          });
        }
      }
    }

    // Account ban status — priority: MMR 403/404 with real ban error > userInfo.accountStatus > userInfo.ban flag
    let accountStatus: string | null = "Active";

    const mmrBan = (mmrData as Record<string, unknown>)?.__ban__;
    if (mmrBan === true) {
      const errBody = (mmrData as Record<string, unknown>).__errorBody__ as string ?? "";
      const errUpper = errBody.toUpperCase();
      if (errUpper.includes("ACCESS_DENIED") || errUpper.includes("FORBIDDEN")) {
        accountStatus = "BANNED (Access Denied)";
      } else if (errUpper.includes("TEMPORARY")) {
        accountStatus = "TEMPORAL BAN (Time Ban)";
      } else {
        accountStatus = "BANNED";
      }
    } else if (typeof userInfo?.accountStatus === "string" && userInfo.accountStatus !== "Active") {
      accountStatus = userInfo.accountStatus;
    } else if (userInfo?.ban && typeof userInfo.ban === "object") {
      const b = userInfo.ban as Record<string, unknown>;
      // Check restrictions array first (new Riot API)
      const restrictions = Array.isArray(b.restrictions) ? b.restrictions : [];
      if (restrictions.length > 0) {
        const r = restrictions[0] as Record<string, unknown>;
        const reason = typeof r.reason === "string" ? r.reason : "";
        const type = typeof r.type === "string" ? r.type : "";
        accountStatus = reason ? `BANNED: ${reason}` : `BANNED: ${type}`;
      } else {
        // Legacy ban.flag fallback
        const flag = typeof b.flag === "string" ? b.flag : null;
        const restUntil = typeof b.rest_until === "number" ? b.rest_until : null;
        if (flag) {
          accountStatus = restUntil
            ? `Suspended until ${new Date(restUntil).toLocaleDateString("vi-VN")}`
            : `BANNED: ${flag}`;
        }
      }
    } else if (userInfo?.AccountFlag && userInfo.AccountFlag !== 0) {
      accountStatus = `FLAGGED: ${userInfo.AccountFlag}`;
    }

    // Map error codes to human-readable labels
    const RESTRICTION_LABELS: Record<string, string> = {
      "OG_ANALYTICAL_PERMANENT":    "OG Analytical Permanent",
      "AC_SCRIPTING_PERMANENT":     "Anti-Cheat Scripting Permanent",
      "AC_SCRIPTING_TEMPORARY":      "Anti-Cheat Scripting Temporary",
      "COMPETITIVE_TEMPORARY":       "Competitive Queue Temporary",
      "COMPETITIVE_GAMEPLAY_REPORT": "Competitive Gameplay Report",
      "CHAT_2":                      "Chat Restriction (2-day)",
      "CHAT_7":                      "Chat Restriction (7-day)",
      "CHAT_30":                     "Chat Restriction (30-day)",
      "QUEUE_2":                     "Queue Lock (2 days)",
      "QUEUE_7":                     "Queue Lock (7 days)",
      "QUEUE_30":                    "Queue Lock (30 days)",
      "QUEUE_PERMANENT":             "Queue Lock Permanent",
      "NAME_REVIEW":                 "Name Under Review",
      "DISCONNECTOR":                "Leaver/Disconnect Penalty",
      "SENDPAC_2":                   "Sent PAC Penalty (2 games)",
      "SENDPAC_5":                   "Sent PAC Penalty (5 games)",
      "SENDPAC_10":                  "Sent PAC Penalty (10 games)",
      "SENDPAC_20":                  "Sent PAC Penalty (20 games)",
    };

    // Ranked restrictions
    let rankedRestriction: string | null = null;
    const rawRestrictions = (restrictionsData as Record<string, unknown>).restrictions as Array<Record<string, unknown>> | undefined;
    if (Array.isArray(rawRestrictions) && rawRestrictions.length > 0) {
      rankedRestriction = rawRestrictions.map((r) => {
        const type = (r.type as string) ?? "";
        const reason = (r.reason as string) ?? "";
        const key = type || reason;
        return RESTRICTION_LABELS[key] ?? (key ? `Restricted: ${key}` : "Restricted");
      }).join("; ") || null;
    } else if ((restrictionsData as Record<string, unknown>).errorCode) {
      const ec = (restrictionsData as Record<string, unknown>).errorCode as string;
      const em = ((restrictionsData as Record<string, unknown>).errorMsg as string) ?? "";
      rankedRestriction = RESTRICTION_LABELS[ec] ?? `[${ec}] ${em}`;
    }

    // Banned account — return early without rank data
    if ((mmrData as Record<string, unknown>)?.__ban__ === true) {
      return NextResponse.json({
        currentRank: "—",
        currentIcon: "",
        currentRR: 0,
        peakRank: "—",
        peakIcon: "",
        peakRR: 0,
        seasonLabel: "—",
        accountLevel,
        createdAt,
        lastActivity,
        accountStatus,
        rankedRestriction,
      });
    }

    // No rank data (not banned, just no competitive data yet)
    // Check if it's a token/auth issue vs genuinely unrated
    // __ban__: false + __status__: 404 = account genuinely has no competitive data (new/unranked account)
    // __ban__: false + __status__: 403 = token might be invalid
    // No __status__ at all = unexpected response
    const hasMMR = (mmrData as Record<string, unknown>)?.LatestCompetitiveUpdate;
    const hasHistory = (mmrData as Record<string, unknown>)?.__hasCompetitiveHistory__;
    if (!mmrData || (!hasMMR && !hasHistory)) {
      const mmrStatus = (mmrData as Record<string, unknown>)?.__status__ as number | undefined;
      const hasBan = (mmrData as Record<string, unknown>)?.__ban__;
      const hasError = (mmrData as Record<string, unknown>)?.error;
      const errBody = (mmrData as Record<string, unknown>)?.__errorBody__ as string | undefined;
      const noRankReason = (mmrStatus === 404 && hasBan === false)
        ? "Chua choi ranked hoac tich hop du lieu"
        : (mmrStatus === 403 || hasError)
        ? "Token khong hop le hoac het han — vui long dang nhap lai"
        : mmrStatus === 401
        ? "Token het han — can dang nhap lai"
        : "Chua choi ranked hoac tich hop du lieu";

      console.log("[MMR no-data] mmrStatus:", mmrStatus, "hasBan:", hasBan, "hasError:", hasError, "errBody:", errBody, "keys:", Object.keys(mmrData ?? {}), "region:", region);

      return NextResponse.json({
        currentRank: "—",
        currentIcon: "",
        currentRR: 0,
        peakRank: "—",
        peakIcon: "",
        peakRR: 0,
        seasonLabel: noRankReason,
        accountLevel,
        createdAt,
        lastActivity,
        accountStatus,
        rankedRestriction,
        _debug: { mmrStatus, hasBan, hasError, errBody, region },
      });
    }

    // Use LatestCompetitiveUpdate if available, otherwise fall back to competitive history match
    let comp: Record<string, unknown> | undefined = mmrData.LatestCompetitiveUpdate;
    let tier = 0, rr = 0, seasonId = "";

    if (!comp && mmrData?.__hasCompetitiveHistory__) {
      const histMatches = mmrData.CompetitiveStats?.Matches as Array<Record<string, unknown>> | undefined;
      if (Array.isArray(histMatches) && histMatches.length > 0) {
        comp = histMatches[0];
        tier = (comp?.TierAfterUpdate as number) ?? 0;
        rr = (comp?.RankedRatingAfterUpdate as number) ?? 0;
        seasonId = (comp?.SeasonID as string) ?? "";
      }
    } else {
      tier = (comp?.TierAfterUpdate as number) ?? 0;
      rr = (comp?.RankedRatingAfterUpdate as number) ?? 0;
      seasonId = (comp?.SeasonID as string) ?? "";
    }

    const peakTier = mmrData.HighestRankedUpdate?.TierAfterUpdate ?? tier;
    const peakRR = mmrData.HighestRankedUpdate?.RankedRatingAfterUpdate ?? 0;

    const tierInfo = rankTiers.find((t) => t.tier === tier);
    const peakTierInfo = rankTiers.find((t) => t.tier === peakTier);

    let seasonLabel = "Current Season";
    if (seasonId.includes("e6a")) seasonLabel = "Episode 6 Act 3";
    else if (seasonId.includes("e5a")) seasonLabel = "Episode 5 Act 3";
    else if (seasonId.includes("e4a")) seasonLabel = "Episode 4 Act 3";
    else if (seasonId.includes("e3a")) seasonLabel = "Episode 3 Act 3";
    else if (seasonId.includes("e2a")) seasonLabel = "Episode 2 Act 3";
    else if (seasonId.includes("e1a")) seasonLabel = "Episode 1 Act 3";

    return NextResponse.json({
      currentRank: tierInfo?.tierName ?? `Rank ${tier}`,
      currentIcon: tierInfo?.largeIcon ?? "",
      currentRR: rr,
      peakRank: peakTierInfo?.tierName ?? `Rank ${peakTier}`,
      peakIcon: peakTierInfo?.largeIcon ?? "",
      peakRR: peakRR,
      seasonLabel,
      accountLevel,
      createdAt,
      lastActivity,
      accountStatus,
      rankedRestriction,
    });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    if (msg.includes("401")) return NextResponse.json({ error: "Token hết hạn" }, { status: 401 });
    if (msg.includes("404")) return NextResponse.json({ error: "Không tìm thấy dữ liệu rank" }, { status: 404 });
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
