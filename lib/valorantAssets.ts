interface ValorantVersion {
  data: {
    riotClientVersion: string;
    valorantClientVersion: string;
  };
}

interface SkinLevel {
  uuid: string;
  displayName: string;
  displayIcon: string;
  assetPath?: string;
}

interface Weapon {
  uuid: string;
  displayName: string;
  displayIcon: string;
  skinLevels: SkinLevel[];
}

interface Agent {
  uuid: string;
  displayName: string;
  displayIcon: string;
  smallIcon: string;
  role?: {
    displayName: string;
  };
}

interface Spray {
  uuid: string;
  displayName: string;
  displayIcon: string;
}

interface PlayerCard {
  uuid: string;
  displayName: string;
  displayIcon: string;
}

interface BuddyLevel {
  uuid: string;
  displayName: string;
  displayIcon: string;
  levels?: {
    uuid: string;
    displayName: string;
    displayIcon: string;
  }[];
}

interface CompetitiveTier {
  uuid: string;
  tiers: {
    tier: number;
    tierName: string;
    smallIcon: string;
    largeIcon: string;
    triangleDownIcon: string;
  }[];
}

let cachedVersion: string | null = null;
let cachedSkinMap: Map<string, SkinLevel> | null = null;
let cachedWeaponMap: Map<string, string> | null = null;
let cachedAgentMap: Map<string, Agent> | null = null;
let cachedSprayMap: Map<string, Spray> | null = null;
let cachedCardMap: Map<string, PlayerCard> | null = null;
let cachedBuddyMap: Map<string, BuddyLevel> | null = null;
let cachedRankMap: CompetitiveTier | null = null;

export async function getValorantVersion(): Promise<string> {
  if (cachedVersion) return cachedVersion;
  try {
    const res = await fetch(
      "https://valorant-api.com/v1/version",
      { next: { revalidate: 3600 } }
    );
    const json: ValorantVersion = await res.json();
    cachedVersion = json.data.riotClientVersion;
    return cachedVersion;
  } catch {
    return "shipping-14-10-19-17-40-14-bugfix";
  }
}

export async function getSkinMap(): Promise<Map<string, SkinLevel>> {
  if (cachedSkinMap) return cachedSkinMap;
  try {
    const res = await fetch(
      "https://valorant-api.com/v1/weapons/skinlevels",
      { next: { revalidate: 86400 } }
    );
    const json = await res.json();
    cachedSkinMap = new Map();
    for (const skin of json.data as SkinLevel[]) {
      cachedSkinMap.set(skin.uuid, skin);
    }
    return cachedSkinMap;
  } catch {
    cachedSkinMap = new Map();
    return cachedSkinMap;
  }
}

export async function getWeaponSkinMap(): Promise<Map<string, string>> {
  if (cachedWeaponMap) return cachedWeaponMap;
  try {
    const res = await fetch(
      "https://valorant-api.com/v1/weapons",
      { next: { revalidate: 86400 } }
    );
    const json = await res.json();
    cachedWeaponMap = new Map();
    for (const weapon of json.data as Weapon[]) {
      for (const level of weapon.skinLevels ?? []) {
        cachedWeaponMap.set(level.uuid, weapon.displayName);
      }
    }
    return cachedWeaponMap;
  } catch {
    cachedWeaponMap = new Map();
    return cachedWeaponMap;
  }
}

export async function getAgentMap(): Promise<Map<string, Agent>> {
  if (cachedAgentMap) return cachedAgentMap;
  try {
    const res = await fetch(
      "https://valorant-api.com/v1/agents?isPlayableCharacter=true",
      { next: { revalidate: 86400 } }
    );
    const json = await res.json();
    cachedAgentMap = new Map();
    for (const agent of json.data as Agent[]) {
      cachedAgentMap.set(agent.uuid, agent);
    }
    return cachedAgentMap;
  } catch {
    cachedAgentMap = new Map();
    return cachedAgentMap;
  }
}

export async function getSprayMap(): Promise<Map<string, Spray>> {
  if (cachedSprayMap) return cachedSprayMap;
  try {
    const res = await fetch(
      "https://valorant-api.com/v1/sprays",
      { next: { revalidate: 86400 } }
    );
    const json = await res.json();
    cachedSprayMap = new Map();
    for (const spray of json.data as Spray[]) {
      cachedSprayMap.set(spray.uuid, spray);
    }
    return cachedSprayMap;
  } catch {
    cachedSprayMap = new Map();
    return cachedSprayMap;
  }
}

export async function getCardMap(): Promise<Map<string, PlayerCard>> {
  if (cachedCardMap) return cachedCardMap;
  try {
    const res = await fetch(
      "https://valorant-api.com/v1/playercards",
      { next: { revalidate: 86400 } }
    );
    const json = await res.json();
    cachedCardMap = new Map();
    for (const card of json.data as PlayerCard[]) {
      cachedCardMap.set(card.uuid, card);
    }
    return cachedCardMap;
  } catch {
    cachedCardMap = new Map();
    return cachedCardMap;
  }
}

export async function getBuddyMap(): Promise<Map<string, BuddyLevel>> {
  if (cachedBuddyMap) return cachedBuddyMap;
  try {
    const res = await fetch(
      "https://valorant-api.com/v1/buddies/levels",
      { next: { revalidate: 86400 } }
    );
    const json = await res.json();
    cachedBuddyMap = new Map();
    for (const level of json.data as BuddyLevel[]) {
      cachedBuddyMap.set(level.uuid, level);
    }
    return cachedBuddyMap;
  } catch {
    cachedBuddyMap = new Map();
    return cachedBuddyMap;
  }
}

export async function getRankMap(): Promise<CompetitiveTier> {
  if (cachedRankMap) return cachedRankMap;
  try {
    const res = await fetch(
      "https://valorant-api.com/v1/competitivetiers",
      { next: { revalidate: 86400 } }
    );
    const json = await res.json();
    cachedRankMap = json.data[json.data.length - 1] as CompetitiveTier;
    return cachedRankMap;
  } catch {
    return {
      uuid: "",
      tiers: [],
    };
  }
}

export interface ValorantAssets {
  version: string;
  skinMap: Map<string, SkinLevel>;
  weaponMap: Map<string, string>;
  agentMap: Map<string, Agent>;
  sprayMap: Map<string, Spray>;
  cardMap: Map<string, PlayerCard>;
  buddyMap: Map<string, BuddyLevel>;
  rankMap: CompetitiveTier;
}

export async function loadAllAssets(): Promise<ValorantAssets> {
  const [version, skinMap, weaponMap, agentMap, sprayMap, cardMap, buddyMap, rankMap] =
    await Promise.all([
      getValorantVersion(),
      getSkinMap(),
      getWeaponSkinMap(),
      getAgentMap(),
      getSprayMap(),
      getCardMap(),
      getBuddyMap(),
      getRankMap(),
    ]);
  return { version, skinMap, weaponMap, agentMap, sprayMap, cardMap, buddyMap, rankMap };
}
