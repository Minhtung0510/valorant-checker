import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { username, password } = body;

    if (!username || !password) {
      return NextResponse.json({ error: "Missing username or password" }, { status: 400 });
    }

    // Riot Client local API — only works when Valorant/Riot Client is running
    const authRes = await fetch("https://127.0.0.1:52273/auth/v1/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!authRes.ok) {
      const text = await authRes.text();
      if (authRes.status === 429) {
        return NextResponse.json({ error: "Quá nhiều yêu cầu. Thử lại sau 5 phút." }, { status: 429 });
      }
      return NextResponse.json({ error: `Đăng nhập thất bại (${authRes.status}). Kiểm tra lại tài khoản.` }, { status: 401 });
    }

    const authData = await authRes.json();
    const accessToken = authData.access_token;

    if (!accessToken) {
      return NextResponse.json({ error: "Không nhận được access token. Đảm bảo Valorant/Riot Client đang chạy." }, { status: 500 });
    }

    // Get entitlement token
    const entRes = await fetch("https://127.0.0.1:52273/entitlements/v1/token", {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
    });

    let entitlementToken = "";
    if (entRes.ok) {
      const entData = await entRes.json();
      entitlementToken = entData.entitlements_token ?? "";
    }

    // Get user info
    let userInfo: Record<string, unknown> = {};
    const uiRes = await fetch("https://auth.riotgames.com/userinfo", {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (uiRes.ok) userInfo = await uiRes.json();

    return NextResponse.json({
      accessToken,
      entitlementToken,
      puuid: userInfo.sub ?? "",
      gameName: userInfo.game_name ?? username,
      tagLine: userInfo.tag_line ?? "",
    });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Unknown error";
    if (msg.includes("fetch") || msg.includes("ERR_CONNECTION")) {
      return NextResponse.json({ error: "Riot Client không chạy. Hãy mở Valorant trước (kể cả chỉ để nền)." }, { status: 503 });
    }
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
