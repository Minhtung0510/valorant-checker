import { NextRequest, NextResponse } from "next/server";
import { createSession } from "@/lib/authStore";
import { fetchEntitlementToken, fetchUserInfo } from "@/lib/riotApi";

/**
 * GET /api/auth/callback
 *
 * Riot redirects here after user approves login.
 * Exchanges auth code for tokens and creates a long-lived session.
 *
 * Expected query params:
 *   code         — authorization code from Riot
 *   state        — opaque state for CSRF (we pass puuid-region as session hint)
 *   error        — if user denied consent
 */
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const code = searchParams.get("code");
  const state = searchParams.get("state");
  const error = searchParams.get("error");

  if (error || !code) {
    const reason = error || "missing_code";
    return NextResponse.redirect(
      new URL(`/auth?error=${encodeURIComponent(reason)}`, req.url)
    );
  }

  // Client ID for the Riot client integration
  const RIOT_CLIENT_ID = "riot-client";
  const REDIRECT_URI = `${req.nextUrl.origin}/api/auth/callback`;

  try {
    // Step 1: Exchange code for tokens
    const tokenRes = await fetch(
      "https://auth.riotgames.com/token",
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          grant_type: "authorization_code",
          code,
          redirect_uri: REDIRECT_URI,
          client_id: RIOT_CLIENT_ID,
        }),
      }
    );

    if (!tokenRes.ok) {
      const text = await tokenRes.text();
      console.error("[auth/callback] Token exchange failed:", text);
      return NextResponse.redirect(
        new URL(`/auth?error=token_exchange_failed`, req.url)
      );
    }

    const tokenData = await tokenRes.json() as {
      access_token: string;
      refresh_token: string;
      expires_in: number;
      refresh_token_expires_in?: number;
      id_token?: string;
    };

    const accessToken = tokenData.access_token;
    const refreshToken = tokenData.refresh_token;
    const expiresIn = tokenData.expires_in ?? 3600;

    // Riot returns refresh_token_expires_in in ms; fall back to 30 days if not provided.
    // Using the real value ensures token lifecycle detection works correctly.
    const refreshExpiresIn = (tokenData.refresh_token_expires_in ?? 30 * 24 * 60 * 60 * 1000) / 1000;

    // Step 2: Get user info to extract game name, tag line, puuid, region
    const userInfo = (await fetchUserInfo(accessToken)) as Record<string, unknown>;

    const puuid = (userInfo?.sub as string) ?? "";
    const gameName = (userInfo?.acct as Record<string, unknown>)?.game_name as string ?? "Unknown";
    const tagLine = (userInfo?.acct as Record<string, unknown>)?.tag_line as string ?? "";
    const region = typeof userInfo?.region === "string" ? userInfo.region.toUpperCase() : "AP";

    // Step 3: Get entitlement token
    const entitlementToken = await fetchEntitlementToken(accessToken);

    // Step 4: Create session
    const sessionId = createSession({
      gameName,
      tagLine,
      puuid,
      region,
      accessToken,
      refreshToken,
      entitlementToken,
      expiresIn,
      refreshExpiresIn,
    });

    // Step 5: Redirect to auth page with session ID
    // The state param we sent earlier contains region (e.g. "AP" or "NA")
    const targetRegion = state && /^[A-Z]{2}$/.test(state) ? state : region;
    return NextResponse.redirect(
      new URL(`/auth?sid=${sessionId}&region=${targetRegion}`, req.url)
    );
  } catch (e) {
    console.error("[auth/callback] Unexpected error:", e);
    return NextResponse.redirect(
      new URL(`/auth?error=server_error`, req.url)
    );
  }
}
