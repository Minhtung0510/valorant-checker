import { NextRequest, NextResponse } from "next/server";
import { deleteSession } from "@/lib/authStore";

/**
 * POST /api/auth/delete
 * Body: { sessionId: string }
 * Deletes the session from the store.
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { sessionId } = body as { sessionId?: string };
    if (!sessionId) {
      return NextResponse.json({ error: "Missing sessionId" }, { status: 400 });
    }
    deleteSession(sessionId);
    return NextResponse.json({ ok: true });
  } catch (e) {
    console.error("[auth/delete]", e);
    return NextResponse.json({ error: "Server error" }, { status: 500 });
  }
}
