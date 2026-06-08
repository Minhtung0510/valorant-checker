import { NextRequest, NextResponse } from "next/server";
import { fetchRank, fetchRankTiers, fetchUserInfo, fetchRankedRestrictions } from "@/lib/riotApi";
import type { Region } from "@/lib/types";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { accessToken, entitlementToken, version, puuid, region } = body;

    if (!accessToken || !entitlementToken || !puuid || !region) {
      return NextResponse.json({ error: "Missing required fields" }, { status: 400 });
    }

    const [mmrData, rankTiers, userInfo, restrictionsData] = await Promise.all([
      fetchRank(accessToken, entitlementToken, version, puuid, region as Region),
      fetchRankTiers(),
      fetchUserInfo(accessToken),
      fetchRankedRestrictions(accessToken, entitlementToken, version, puuid, region as Region),
    ]);

    // Account level from mmr response
    const accountLevel = mmrData?.AccountLevel ?? 0;

    // Account creation + last activity + status from userinfo
    const createdAt = userInfo?.acct?.created_at
      ? new Date(userInfo.acct.created_at).toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric" })
      : null;

    // Last competitive activity
    let lastActivity: string | null = null;
    if (mmrData?.LatestCompetitiveUpdate?.MatchStartTime) {
      lastActivity = new Date(mmrData.LatestCompetitiveUpdate.MatchStartTime).toLocaleString("vi-VN", {
        day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit",
      });
    }

    // Account ban status — priority: MMR 403/404 > userInfo.accountStatus > userInfo.ban flag
    let accountStatus: string | null = "Active";

    if ((mmrData as Record<string, unknown>)?.__ban__ === true) {
      accountStatus = "BANNED";
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

    // Ranked restrictions
    let rankedRestriction: string | null = null;
    const rawRestrictions = (restrictionsData as Record<string, unknown>).restrictions as Array<Record<string, unknown>> | undefined;
    if (Array.isArray(rawRestrictions) && rawRestrictions.length > 0) {
      const types = rawRestrictions.map((r) => (r.type as string) || (r.reason as string)).filter(Boolean);
      rankedRestriction = types.join("; ") || null;
    } else if ((restrictionsData as Record<string, unknown>).errorCode) {
      rankedRestriction = `[${(restrictionsData as Record<string, unknown>).errorCode}] ${((restrictionsData as Record<string, unknown>).errorMsg as string) ?? ""}`;
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

    if (!mmrData) {
      return NextResponse.json({
        currentRank: "Unrated",
        currentIcon: "",
        currentRR: 0,
        peakRank: "Unrated",
        peakIcon: "",
        peakRR: 0,
        seasonLabel: "Current Season",
        accountLevel,
        createdAt,
        lastActivity,
        accountStatus,
        rankedRestriction,
      });
    }

    const comp = mmrData.LatestCompetitiveUpdate;
    const tier = comp?.TierAfterUpdate ?? 0;
    const rr = comp?.RankedRatingAfterUpdate ?? 0;
    const peakTier = mmrData.HighestRankedUpdate?.TierAfterUpdate ?? tier;
    const peakRR = mmrData.HighestRankedUpdate?.RankedRatingAfterUpdate ?? 0;
    const seasonId = comp?.SeasonID ?? "";

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
