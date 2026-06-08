import { NextRequest, NextResponse } from "next/server";
import { fetchAccountXp } from "@/lib/riotApi";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { accessToken, entitlementToken, version, puuid, region } = body;

    if (!accessToken || !entitlementToken || !puuid || !region) {
      return NextResponse.json({ error: "Missing required fields" }, { status: 400 });
    }

    const data = await fetchAccountXp(accessToken, entitlementToken, version, puuid, region as import("@/lib/types").Region);
    return NextResponse.json(data);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    if (msg.includes("401")) return NextResponse.json({ error: "Token hết hạn" }, { status: 401 });
    if (msg.includes("404")) return NextResponse.json({ error: "Không tìm thấy dữ liệu" }, { status: 404 });
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
