import { NextRequest, NextResponse } from "next/server";
import { getAllSessions, deleteSession } from "@/lib/authStore";

/**
 * GET /api/auth/sessions
 * Returns all active sessions (public info only — no tokens).
 *
 * POST /api/auth/sessions
 * { action: "delete", sessionId: string }
 */
export async function GET() {
  const sessions = getAllSessions();
  return NextResponse.json({
    sessions: sessions.map((s) => ({
      sessionId: s.sessionId,
      gameName: s.gameName,
      tagLine: s.tagLine,
      puuid: s.puuid,
      region: s.region,
      createdAt: new Date(s.createdAt).toLocaleString("vi-VN"),
      expiresAt: new Date(s.refreshExpiresAt).toLocaleString("vi-VN"),
      isExpired: s.refreshExpiresAt < Date.now(),
    })),
  });
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { action, sessionId } = body as { action?: string; sessionId?: string };

    if (action === "delete" && sessionId) {
      deleteSession(sessionId);
      return NextResponse.json({ ok: true });
    }

    return NextResponse.json({ error: "Unknown action" }, { status: 400 });
  } catch (e) {
    console.error("[auth/sessions]", e);
    return NextResponse.json({ error: "Server error" }, { status: 500 });
  }
}
