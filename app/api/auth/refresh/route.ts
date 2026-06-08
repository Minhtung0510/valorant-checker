import { NextRequest, NextResponse } from "next/server";
import { getSession, updateSession } from "@/lib/authStore";
import { fetchEntitlementToken } from "@/lib/riotApi";

/**
 * POST /api/auth/refresh
 *
 * Refreshes the access token and entitlement token for a session.
 * Should be called automatically by API routes when token is expired/close to expiry.
 *
 * Body: { sessionId: string }
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { sessionId } = body as { sessionId?: string };

    if (!sessionId) {
      return NextResponse.json({ error: "Missing sessionId" }, { status: 400 });
    }

    const session = getSession(sessionId);
    if (!session) {
      return NextResponse.json({ error: "Session not found or expired" }, { status: 404 });
    }

    const RIOT_CLIENT_ID = "riot-client";

    // Step 1: Exchange refresh token for new access token
    const tokenRes = await fetch(
      "https://auth.riotgames.com/token",
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          grant_type: "refresh_token",
          refresh_token: session.refreshToken,
          client_id: RIOT_CLIENT_ID,
        }),
      }
    );

    if (!tokenRes.ok) {
      const text = await tokenRes.text();
      console.error("[auth/refresh] Refresh failed:", text);
      return NextResponse.json(
        { error: "Token refresh failed. Please re-login." },
        { status: 401 }
      );
    }

    const tokenData = await tokenRes.json() as {
      access_token: string;
      refresh_token: string;
      expires_in: number;
    };

    const newAccessToken = tokenData.access_token;
    const newRefreshToken = tokenData.refresh_token ?? session.refreshToken;
    const expiresIn = tokenData.expires_in ?? 3600;

    // Step 2: Fetch new entitlement token
    const newEntitlementToken = await fetchEntitlementToken(newAccessToken);

    // Step 3: Update session
    updateSession(sessionId, {
      accessToken: newAccessToken,
      refreshToken: newRefreshToken,
      expiresAt: Date.now() + expiresIn * 1000,
      entitlementToken: newEntitlementToken,
    });

    return NextResponse.json({
      accessToken: newAccessToken,
      entitlementToken: newEntitlementToken,
      expiresAt: Date.now() + expiresIn * 1000,
    });
  } catch (e) {
    console.error("[auth/refresh] Unexpected error:", e);
    return NextResponse.json({ error: "Server error" }, { status: 500 });
  }
}
