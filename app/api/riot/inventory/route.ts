import { NextRequest, NextResponse } from "next/server";
import { fetchInventory } from "@/lib/riotApi";
import { ITEM_TYPE_UUIDS, type Region } from "@/lib/types";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { accessToken, entitlementToken, version, puuid, region, itemType } = body;

    if (!accessToken || !entitlementToken || !puuid || !region || !itemType) {
      return NextResponse.json({ error: "Missing required fields" }, { status: 400 });
    }

    const uuidMap: Record<string, string> = {
      skins: ITEM_TYPE_UUIDS.skinLevels,
      buddies: ITEM_TYPE_UUIDS.buddies,
      agents: ITEM_TYPE_UUIDS.agents,
      cards: ITEM_TYPE_UUIDS.playerCards,
      sprays: ITEM_TYPE_UUIDS.sprays,
    };

    const itemTypeUuid = uuidMap[itemType];
    if (!itemTypeUuid) {
      return NextResponse.json({ error: "Invalid item type" }, { status: 400 });
    }

    const entitlementsData = await fetchInventory(
      accessToken, entitlementToken, version, puuid, region as Region, itemTypeUuid
    );

    if (itemType !== "skins") {
      const { fetchAgents, fetchPlayerCards, fetchBuddies, fetchSprays } = await import("@/lib/riotApi");
      let assetMap: Map<string, { name: string; icon: string }> = new Map();
      if (itemType === "agents") assetMap = await fetchAgents() as Map<string, { name: string; icon: string }>;
      else if (itemType === "cards") assetMap = await fetchPlayerCards() as Map<string, { name: string; icon: string; large: string; wide: string }>;
      else if (itemType === "buddies") assetMap = await fetchBuddies() as Map<string, { name: string; icon: string }>;
      else if (itemType === "sprays") assetMap = await fetchSprays() as Map<string, { name: string; icon: string }>;

      const entitlements = entitlementsData.Entitlements ?? [];
      const items = entitlements.map((ent: { ItemID: string }) => {
        const info = assetMap.get(ent.ItemID);
        if (itemType === "cards") {
          const cardInfo = info as { name: string; icon: string; large: string; wide: string } | undefined;
          return { uuid: ent.ItemID, name: cardInfo?.name ?? "Unknown", icon: cardInfo?.icon ?? "", type: itemType, large: cardInfo?.large ?? "", wide: cardInfo?.wide ?? "" };
        }
        return { uuid: ent.ItemID, name: info?.name ?? "Unknown", icon: info?.icon ?? "", type: itemType };
      }).filter((item: { name: string }) => item.name !== "Unknown");

      return NextResponse.json({ items });
    }

    // ============ SKINS ============
    const [skinsRes, levelsRes, tiersRes] = await Promise.all([
      fetch("https://valorant-api.com/v1/weapons/skins", { cache: "no-store" }),
      fetch("https://valorant-api.com/v1/weapons/skinlevels", { cache: "no-store" }),
      fetch("https://valorant-api.com/v1/contenttiers", { cache: "no-store" }),
    ]);

    const skinsData = await skinsRes.json();
    const levelsData = await levelsRes.json();
    const tiersData = await tiersRes.json();

    // Build contentTierUuid -> { name, icon }
    const tierMap = new Map<string, { rarity: string; rarityIcon: string }>();
    for (const tier of tiersData.data ?? []) {
      tierMap.set(tier.uuid, {
        rarity: tier.devName ?? tier.displayName ?? "",
        rarityIcon: tier.displayIcon ?? "",
      });
    }

    // levelUuid -> { baseSkinName, contentTierUuid }
    const levelToBaseName = new Map<string, string>();
    const levelToTier = new Map<string, string>();
    for (const skin of skinsData.data ?? []) {
      const baseName = skin.displayName;
      const tierUuid = skin.contentTierUuid ?? "";
      for (const level of skin.levels ?? []) {
        levelToBaseName.set(level.uuid, baseName);
        if (tierUuid) levelToTier.set(level.uuid, tierUuid);
      }
    }

    // levelUuid -> icon from levels endpoint
    const levelToLevelIcon = new Map<string, string>();
    for (const weapon of levelsData.data ?? []) {
      for (const level of weapon.skinLevels ?? []) {
        levelToLevelIcon.set(level.uuid, level.displayIcon ?? "");
      }
    }

    // skin displayName -> icon from skins endpoint (base icon, always present)
    const baseNameToIcon = new Map<string, string>();
    for (const skin of skinsData.data ?? []) {
      const icon = skin.displayIcon
        ?? skin.levels?.[0]?.displayIcon
        ?? skin.chromaImage
        ?? skin.levels?.[0]?.fullRender
        ?? "";
      baseNameToIcon.set(skin.displayName, icon);
    }

    // Process entitlements: deduplicate by baseSkinName
    const entitlements = entitlementsData.Entitlements ?? [];
    const seen = new Set<string>();

    const items: Array<{ uuid: string; name: string; icon: string; type: string; rarity: string; rarityIcon: string }> = [];

    for (const ent of entitlements) {
      const baseName = levelToBaseName.get(ent.ItemID);
      if (!baseName || seen.has(baseName)) continue;
      seen.add(baseName);

      const levelIcon = levelToLevelIcon.get(ent.ItemID) ?? "";
      const baseIcon = baseNameToIcon.get(baseName) ?? "";
      const icon = levelIcon || baseIcon;
      const tierUuid = levelToTier.get(ent.ItemID) ?? "";
      const tierInfo = tierMap.get(tierUuid);
      const rarity = tierInfo?.rarity ?? "";
      const rarityIcon = tierInfo?.rarityIcon ?? "";

      items.push({ uuid: ent.ItemID, name: baseName, icon, type: "skins", rarity, rarityIcon });
    }

    return NextResponse.json({ items, levelCount: entitlements.length });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    if (msg.includes("401")) return NextResponse.json({ error: "Token hết hạn" }, { status: 401 });
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
