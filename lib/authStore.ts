/**
 * authStore.ts — JSON-file based session store for long-lived Riot tokens.
 *
 * Session lifecycle:
 *   1. User lands on /auth → clicks "Login with Riot" → redirected to Riot
 *   2. Riot redirects to /api/auth/callback?code=xxx
 *   3. Callback exchanges code → gets access_token + refresh_token → saves session
 *   4. Frontend reads session ID → passes it to dashboard
 *   5. All API routes read session → auto-refresh token when needed
 *
 * Session file lives at DATA_DIR/auth_sessions.json (next to .env)
 */

import fs from "fs";
import path from "path";
import { randomUUID } from "crypto";

const DATA_DIR = path.join(process.cwd(), "scripts", "python");
const SESSION_FILE = path.join(DATA_DIR, "auth_sessions.json");

export interface StoredSession {
  sessionId: string;
  gameName: string;
  tagLine: string;
  puuid: string;
  region: string;
  accessToken: string;
  refreshToken: string;
  entitlementToken: string;
  expiresAt: number;       // access_token expiry (ms timestamp)
  refreshExpiresAt: number; // refresh_token expiry (ms timestamp)
  createdAt: number;
}

export interface SessionStore {
  [sessionId: string]: StoredSession;
}

function readStore(): SessionStore {
  try {
    if (!fs.existsSync(SESSION_FILE)) return {};
    return JSON.parse(fs.readFileSync(SESSION_FILE, "utf-8")) as SessionStore;
  } catch {
    return {};
  }
}

function writeStore(store: SessionStore): void {
  try {
    if (!fs.existsSync(DATA_DIR)) {
      fs.mkdirSync(DATA_DIR, { recursive: true });
    }
    fs.writeFileSync(SESSION_FILE, JSON.stringify(store, null, 2), "utf-8");
  } catch (e) {
    console.error("[authStore] Failed to write session file:", e);
  }
}

export function createSession(data: {
  gameName: string;
  tagLine: string;
  puuid: string;
  region: string;
  accessToken: string;
  refreshToken: string;
  entitlementToken: string;
  expiresIn: number;
  refreshExpiresIn: number;
}): string {
  const store = readStore();

  // Clean up expired sessions
  const now = Date.now();
  for (const [id, session] of Object.entries(store)) {
    if (session.refreshExpiresAt < now) {
      delete store[id];
    }
  }

  const sessionId = randomUUID();
  const session: StoredSession = {
    sessionId,
    gameName: data.gameName,
    tagLine: data.tagLine,
    puuid: data.puuid,
    region: data.region,
    accessToken: data.accessToken,
    refreshToken: data.refreshToken,
    entitlementToken: data.entitlementToken,
    expiresAt: now + data.expiresIn * 1000,
    refreshExpiresAt: now + data.refreshExpiresIn * 1000,
    createdAt: now,
  };

  store[sessionId] = session;
  writeStore(store);
  return sessionId;
}

export function getSession(sessionId: string): StoredSession | null {
  const store = readStore();
  const session = store[sessionId];
  if (!session) return null;
  if (session.refreshExpiresAt < Date.now()) {
    delete store[sessionId];
    writeStore(store);
    return null;
  }
  return session;
}

export function updateSession(sessionId: string, data: Partial<Pick<StoredSession, "accessToken" | "refreshToken" | "expiresAt" | "entitlementToken">>): StoredSession | null {
  const store = readStore();
  const session = store[sessionId];
  if (!session) return null;
  Object.assign(session, data);
  store[sessionId] = session;
  writeStore(store);
  return session;
}

export function deleteSession(sessionId: string): void {
  const store = readStore();
  delete store[sessionId];
  writeStore(store);
}

export function getAllSessions(): StoredSession[] {
  const store = readStore();
  const now = Date.now();
  return Object.values(store)
    .filter((s) => s.refreshExpiresAt >= now)
    .sort((a, b) => b.createdAt - a.createdAt);
}
