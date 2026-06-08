export interface ParsedToken {
  accessToken: string;
  expiresIn: number;
  expiresAt: number;
}

export interface PlayerInfo {
  sub: string;
  acct: {
    game_name: string;
    tag_line: string;
  };
  region?: string;
}

export interface EntitlementToken {
  entitlements_token: string;
}

export interface WalletBalance {
  vp: number;
  rp: number;
  kingdom_credits: number;
}

export interface SkinOffer {
  offerId: string;
  skinUuid: string;
  skinName: string;
  skinImage: string;
  vpCost: number;
  weaponName: string;
}

export interface BundleOffer {
  bundleUuid: string;
  bundleName: string;
  bundleImage: string;
  vpCost: number;
}

export interface DailyShop {
  skins: SkinOffer[];
  bundle: BundleOffer | null;
}

export type Region = "AP" | "NA" | "EU" | "KR";

export interface RankData {
  currentRank: {
    tier: number;
    division: number;
    rr: number;
    name: string;
    icon: string;
  };
  peakRank: {
    tier: number;
    name: string;
    icon: string;
    act: string;
  };
  seasonInfo: string;
  peakHistory: Array<{
    tier: number;
    name: string;
    icon: string;
    act: string;
  }>;
}

export interface InventoryItem {
  itemUuid: string;
  itemTypeUuid: string;
  name: string;
  image: string;
  rarity?: string;
  weaponName?: string;
}

export interface InventoryData {
  skins: InventoryItem[];
  buddies: InventoryItem[];
  agents: InventoryItem[];
  cards: InventoryItem[];
  sprays: InventoryItem[];
}

export type InventoryTab = "skins" | "buddies" | "agents" | "cards" | "sprays";

export type SkinFilter =
  | "all"
  | "vandal"
  | "phantom"
  | "operator"
  | "sheriff"
  | "ghost"
  | "classic"
  | "melee"
  | "shorty"
  | "bulldog"
  | "guardian"
  | "ares"
  | "odin"
  | "tommy"
  | "knife";

export const ITEM_TYPE_UUIDS = {
  skinLevels: "e7c63390-eda7-46e0-bb7a-a6abdacd2433",
  buddies: "dd3bf334-87f3-40bd-b043-682a57a8dc3a",
  playerCards: "3f296c07-64c3-494c-923b-fe692a4fa1bd",
  sprays: "d5f120f8-ff8c-4aac-92ea-f2b5acbe9475",
  agents: "01bb38e1-da47-4e6a-9b3d-945fe4655707",
} as const;

export const RIOT_CLIENT_PLATFORM =
  "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9";

export const REGION_TO_PD: Record<Region, string> = {
  AP: "ap",
  NA: "na",
  EU: "eu",
  KR: "kr",
};

export const WEAPON_NAME_MAP: Record<string, string> = {
  Vandal: "vandal",
  Phantom: "phantom",
  Operator: "operator",
  Sheriff: "sheriff",
  Ghost: "ghost",
  Classic: "classic",
  Melee: "melee",
  Shorty: "shorty",
  Bulldog: "bulldog",
  Guardian: "guardian",
  Ares: "ares",
  Odin: "odin",
  "Tactical Knife": "knife",
  Knife: "knife",
};
