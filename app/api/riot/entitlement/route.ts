import { NextRequest, NextResponse } from "next/server";
import { fetchEntitlementToken } from "@/lib/riotApi";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { accessToken } = body;

    if (!accessToken || typeof accessToken !== "string") {
      return NextResponse.json({ error: "Missing accessToken" }, { status: 400 });
    }

    const entitlementToken = await fetchEntitlementToken(accessToken);
    return NextResponse.json({ entitlements_token: entitlementToken });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    if (msg.includes("401")) {
      return NextResponse.json({ error: "Token hết hạn hoặc không hợp lệ" }, { status: 401 });
    }
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
