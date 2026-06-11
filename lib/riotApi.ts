import type { Region } from "./types";

export async function fetchEntitlementToken(accessToken: string): Promise<string> {
  const res = await fetch("https://entitlements.auth.riotgames.com/api/token/v1", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: "{}",
  });

  if (!res.ok) throw new Error(`${res.status}`);
  const data = await res.json();
  return data.entitlements_token as string;
}

export async function fetchUserInfo(accessToken: string) {
  const res = await fetch("https://auth.riotgames.com/userinfo", {
    headers: { Authorization: `Bearer ${accessToken}` },
  });

  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

function riotHeaders(accessToken: string, entitlementToken: string, version: string) {
  return {
    Authorization: `Bearer ${accessToken}`,
    "X-Riot-Entitlements-JWT": entitlementToken,
    "X-Riot-ClientVersion": version,
    "X-Riot-ClientPlatform":
      "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9",
  };
}

export async function fetchVersion(): Promise<string> {
  try {
    const res = await fetch("https://valorant-api.com/v1/version", { cache: "no-store" });
    const j = await res.json();
    return j.data.riotClientVersion || "";
  } catch {
    return "";
  }
}

export async function fetchRank(accessToken: string, entitlementToken: string, version: string, puuid: string, region: Region) {
  const pdHost = `pd.${region.toLowerCase()}.a.pvp.net`;
  const res = await fetch(`https://${pdHost}/mmr/v1/players/${puuid}`, {
    headers: riotHeaders(accessToken, entitlementToken, version),
  });

  // 403/404 from MMR = account banned or region locked
  if (res.status === 403 || res.status === 404) {
    const errBody = await res.text();
    console.log("[fetchRank] 403/404 for puuid:", puuid, "status:", res.status, "body:", errBody);
    // Ban thật sự (403 + có BAN/DENIED trong body) vs không có dữ liệu rank (404 RESOURCE_NOT_FOUND)
    const errUpper = errBody.toUpperCase();
    const isRealBan = res.status === 403 && (
      errUpper.includes("BAN") || errUpper.includes("DENIED") || errUpper.includes("ACCESS_DENIED")
    );
    if (isRealBan) {
      return { __ban__: true, __status__: res.status, __errorBody__: errBody };
    }
    // Không phải ban — có thể token hết hạn hoặc chưa có dữ liệu rank
    return { __ban__: false, __status__: res.status };
  }

  if (!res.ok) {
    throw new Error(`${res.status}`);
  }

  const data = await res.json();

  // If main MMR endpoint returns data but no LatestCompetitiveUpdate, try competitive history
  if (data.LatestCompetitiveUpdate) {
    return data;
  }

  // Fallback: fetch competitive history to get latest match data
  const histRes = await fetch(`https://${pdHost}/mmr/v1/players/${puuid}/competitivehistory`, {
    headers: riotHeaders(accessToken, entitlementToken, version),
  });

  if (histRes.ok) {
    const histData = await histRes.json();
    // Re-attach the history to the main data object so the route.ts logic can use it
    return { ...data, CompetitiveStats: histData, __hasCompetitiveHistory__: true };
  }

  // No competitive data available at all
  return data;
}

export async function fetchRankedRestrictions(accessToken: string, entitlementToken: string, version: string, puuid: string, region: Region) {
  const pdHost = `pd.${region.toLowerCase()}.a.pvp.net`;
  const res = await fetch(`https://${pdHost}/restrictions/v1/players/${puuid}/restrictions`, {
    headers: riotHeaders(accessToken, entitlementToken, version),
  });

  if (res.ok) {
    const data = await res.json();
    return { restrictions: data.restrictions ?? [], errorCode: null, errorMsg: null };
  }
  if (res.status === 404) {
    return { restrictions: [], errorCode: null, errorMsg: null };
  }
  if (res.status === 400 || res.status === 403) {
    try {
      const data = await res.json();
      return {
        restrictions: [],
        errorCode: data.errorCode ?? String(res.status),
        errorMsg: data.message ?? "",
      };
    } catch {
      return { restrictions: [], errorCode: String(res.status), errorMsg: "" };
    }
  }
  return { restrictions: [], errorCode: String(res.status), errorMsg: "" };
}

export async function fetchAccountXp(accessToken: string, entitlementToken: string, version: string, puuid: string, region: Region) {
  const pdHost = `pd.${region.toLowerCase()}.a.pvp.net`;
  const res = await fetch(`https://${pdHost}/account-xp/v1/players/${puuid}`, {
    headers: riotHeaders(accessToken, entitlementToken, version),
  });

  if (!res.ok) {
    if (res.status === 404) return null;
    throw new Error(`${res.status}`);
  }

  return res.json();
}

export async function fetchWallet(accessToken: string, entitlementToken: string, version: string, puuid: string, region: Region) {
  const pdHost = `pd.${region.toLowerCase()}.a.pvp.net`;
  const res = await fetch(`https://${pdHost}/store/v1/wallet/${puuid}`, {
    headers: riotHeaders(accessToken, entitlementToken, version),
  });

  if (!res.ok) throw new Error(`${res.status}`);
  const data = await res.json();

  const balances: Record<string, number> = {};
  for (const [uuid, val] of Object.entries(data.Balances ?? {})) {
    balances[uuid] = typeof val === "number" ? val : parseInt(String(val), 10);
  }

  const uuids = Object.keys(balances);
  return {
    valorantPoints:  balances[uuids[0]] ?? 0,
    radianitePoints: balances[uuids[1]] ?? 0,
    kingdomCredits:  balances[uuids[2]] ?? 0,
    freeAgents:      balances[uuids[3]] ?? 0,
    _raw_uuids:      uuids,
  };
}

export async function fetchInventory(accessToken: string, entitlementToken: string, version: string, puuid: string, region: Region, itemTypeUuid: string) {
  const pdHost = `pd.${region.toLowerCase()}.a.pvp.net`;
  const res = await fetch(`https://${pdHost}/store/v1/entitlements/${puuid}/${itemTypeUuid}`, {
    headers: riotHeaders(accessToken, entitlementToken, version),
  });

  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

export async function fetchStorefront(accessToken: string, entitlementToken: string, version: string, puuid: string, region: Region) {
  const pdHost = `pd.${region.toLowerCase()}.a.pvp.net`;
  const res = await fetch(`https://${pdHost}/store/v2/storefront/${puuid}`, {
    headers: riotHeaders(accessToken, entitlementToken, version),
  });

  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

export async function fetchWeaponSkins(): Promise<Map<string, { name: string; icon: string; weapon: string }>> {
  const res = await fetch("https://valorant-api.com/v1/weapons/skins", { cache: "no-store" });
  const j = await res.json();

  // Also fetch skin levels to map level UUID -> skin name (for inventory)
  const levelsRes = await fetch("https://valorant-api.com/v1/weapons/skinlevels", { cache: "no-store" });
  const levelsJ = await levelsRes.json();

  const skinMap = new Map<string, { name: string; icon: string; weapon: string }>();
  const skinLevelsMap = new Map<string, string>(); // levelUuid -> skinName

  // Build level -> skin name mapping
  for (const weapon of levelsJ.data) {
    const weaponName = weapon.displayName;
    const skinName = weapon.displayName; // skin level's displayName is the skin name
    for (const level of weapon.skinLevels ?? []) {
      skinLevelsMap.set(level.uuid, skinName);
    }
  }

  for (const skin of j.data) {
    const icon = skin.displayIcon ?? skin.levels?.[0]?.displayIcon ?? "";
    const firstLevel = skin.levels?.[0];
    const skinName = firstLevel?.displayName ?? skin.displayName;
    // The first level's uuid is the main skin entitlement uuid
    if (firstLevel?.uuid) {
      skinMap.set(firstLevel.uuid, {
        name: skinName,
        icon: firstLevel.displayIcon ?? icon,
        weapon: skin.weapon?.displayName ?? "",
      });
    }
  }

  return skinMap;
}

export async function fetchWeaponSkinLevels(): Promise<Map<string, { name: string; icon: string; weapon: string }>> {
  const res = await fetch("https://valorant-api.com/v1/weapons/skinlevels", { cache: "no-store" });
  const j = await res.json();
  const map = new Map<string, { name: string; icon: string; weapon: string }>();

  const wRes = await fetch("https://valorant-api.com/v1/weapons", { cache: "no-store" });
  const wJ = await wRes.json();
  const weaponNameMap = new Map<string, string>();
  for (const weapon of wJ.data) {
    for (const level of weapon.skinLevels ?? []) {
      weaponNameMap.set(level.uuid, weapon.displayName);
    }
  }

  for (const item of j.data) {
    map.set(item.uuid, {
      name: item.displayName,
      icon: item.displayIcon ?? "",
      weapon: weaponNameMap.get(item.uuid) ?? "",
    });
  }
  return map;
}

export async function fetchAgents(): Promise<Map<string, { name: string; icon: string; role: string }>> {
  const res = await fetch("https://valorant-api.com/v1/agents?isPlayableCharacter=true", { cache: "no-store" });
  const j = await res.json();
  const map = new Map<string, { name: string; icon: string; role: string }>();
  for (const a of j.data) {
    map.set(a.uuid, {
      name: a.displayName,
      icon: a.displayIcon ?? "",
      role: a.role?.displayName ?? "",
    });
  }
  return map;
}

export async function fetchPlayerCards(): Promise<Map<string, { name: string; icon: string; large: string; wide: string }>> {
  const res = await fetch("https://valorant-api.com/v1/playercards", { cache: "no-store" });
  const j = await res.json();
  const map = new Map<string, { name: string; icon: string; large: string; wide: string }>();
  for (const c of j.data) {
    map.set(c.uuid, {
      name: c.displayName,
      icon: c.smallArt ?? c.displayIcon ?? "",
      large: c.largeArt ?? "",
      wide: c.wideArt ?? "",
    });
  }
  return map;
}

export async function fetchBuddies(): Promise<Map<string, { name: string; icon: string }>> {
  const res = await fetch("https://valorant-api.com/v1/buddies/levels", { cache: "no-store" });
  const j = await res.json();
  const map = new Map<string, { name: string; icon: string }>();
  for (const b of j.data) {
    map.set(b.uuid, {
      name: b.displayName,
      icon: b.displayIcon ?? "",
    });
  }
  return map;
}

export async function fetchSprays(): Promise<Map<string, { name: string; icon: string }>> {
  const res = await fetch("https://valorant-api.com/v1/sprays", { cache: "no-store" });
  const j = await res.json();
  const map = new Map<string, { name: string; icon: string }>();
  for (const s of j.data) {
    map.set(s.uuid, {
      name: s.displayName,
      icon: s.displayIcon ?? "",
    });
  }
  return map;
}

export async function fetchRankTiers(): Promise<Array<{ tier: number; tierName: string; largeIcon: string }>> {
  const res = await fetch("https://valorant-api.com/v1/competitivetiers", { cache: "no-store" });
  const j = await res.json();
  const latest = j.data[j.data.length - 1];
  return (latest?.tiers ?? []) as Array<{ tier: number; tierName: string; largeIcon: string }>;
}
