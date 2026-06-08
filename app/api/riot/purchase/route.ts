import { NextRequest, NextResponse } from "next/server";
import type { Region } from "@/lib/types";

function riotHeaders(accessToken: string, entitlementToken: string, version: string) {
  return {
    Authorization: `Bearer ${accessToken}`,
    "X-Riot-Entitlements-JWT": entitlementToken,
    "X-Riot-ClientVersion": version,
    "X-Riot-ClientPlatform":
      "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9",
  };
}

const PAYMENT_METHOD_NAMES: Record<string, string> = {
  paypalrest: "PayPal",
  codashop: "Codashop",
  xsolla: "Xsolla",
  razorpay: "Razorpay",
  stripe: "Stripe",
  "": "Unknown",
  "N/A": "N/A",
};

function formatDate(isoStr: string): string {
  try {
    return new Date(isoStr).toLocaleString("vi-VN", {
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit", second: "2-digit",
    });
  } catch {
    return isoStr;
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { accessToken, entitlementToken, version, puuid, region } = body;

    if (!accessToken || !entitlementToken || !puuid || !region) {
      return NextResponse.json({ error: "Missing required fields" }, { status: 400 });
    }

    const pdHost = `pd.${region.toLowerCase()}.a.pvp.net`;
    const res = await fetch(`https://${pdHost}/store/v1/purchasehistory/${puuid}`, {
      headers: riotHeaders(accessToken, entitlementToken, version),
    });

    if (!res.ok) {
      if (res.status === 404) return NextResponse.json({ history: [] });
      return NextResponse.json({ error: `${res.status}` }, { status: res.status });
    }

    const data = await res.json();
    const raw = data.PurchasedHistory ?? [];

    const history = raw.map((tx: Record<string, unknown>) => ({
      amount: typeof tx.Amount === "string" ? tx.Amount : String(tx.Amount ?? ""),
      currency: typeof tx.Currency === "string" ? tx.Currency : "—",
      date: formatDate(typeof tx.Date === "string" ? tx.Date : ""),
      method: PAYMENT_METHOD_NAMES[tx.PaymentMethod as string] ?? String(tx.PaymentMethod ?? "N/A"),
    }));

    return NextResponse.json({ history });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json({ error: msg, history: [] }, { status: 500 });
  }
}
