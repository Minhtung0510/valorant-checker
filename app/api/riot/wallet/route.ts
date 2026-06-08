import { NextRequest, NextResponse } from "next/server";
import { fetchWallet } from "@/lib/riotApi";
import type { Region } from "@/lib/types";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { accessToken, entitlementToken, version, puuid, region } = body;

    if (!accessToken || !entitlementToken || !puuid || !region) {
      return NextResponse.json({ error: "Missing required fields" }, { status: 400 });
    }

    const data = await fetchWallet(accessToken, entitlementToken, version, puuid, region as Region);
    return NextResponse.json(data);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    if (msg.includes("401")) return NextResponse.json({ error: "Token hết hạn" }, { status: 401 });
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
