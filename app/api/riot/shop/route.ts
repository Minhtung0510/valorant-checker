import { NextRequest, NextResponse } from "next/server";
import { fetchStorefront, fetchWeaponSkinLevels } from "@/lib/riotApi";
import type { Region } from "@/lib/types";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { accessToken, entitlementToken, version, puuid, region } = body;

    if (!accessToken || !entitlementToken || !puuid || !region) {
      return NextResponse.json({ error: "Missing required fields" }, { status: 400 });
    }

    let storefrontData;
    try {
      storefrontData = await fetchStorefront(accessToken, entitlementToken, version, puuid, region as Region);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "";
      if (msg.includes("404")) {
        return NextResponse.json({ offers: [], bundle: null });
      }
      throw e;
    }

    const [skinMap] = await Promise.all([fetchWeaponSkinLevels()]);

    const dailyUuids = storefrontData.SkinsPanelLayout?.SingleItemOffers ?? [];
    const costs = storefrontData.SkinsPanelLayout?.SingleItemOffersCost ?? {};

    const offers = dailyUuids.map((uuid: string) => {
      const info = skinMap.get(uuid);
      return {
        uuid,
        name: info?.name ?? "Unknown",
        icon: info?.icon ?? "",
        vpCost: costs[uuid]?.[0] ?? 0,
        type: "shop",
      };
    });

    const bonusOffers = storefrontData.BonusStore?.BonusStoreOffers ?? [];
    const bundle = bonusOffers.length > 0 ? {
      uuid: bonusOffers[0].BundleItemID,
      name: "Bundle Offer",
      icon: "",
      vpCost: bonusOffers[0].StorefrontItem?.Devices?.SINGLEITEMBUNDLE?.Price?.amount ?? 0,
      type: "bundle",
    } : null;

    return NextResponse.json({ offers, bundle });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    if (msg.includes("401")) return NextResponse.json({ error: "Token hết hạn" }, { status: 401 });
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
