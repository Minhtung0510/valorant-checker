import type { ParsedToken } from "./types";

export function parseRedirectUrl(url: string): ParsedToken | null {
  try {
    const parsed = new URL(url);
    const hash = parsed.hash.substring(1);
    const params = new URLSearchParams(hash);

    const accessToken = params.get("access_token");
    const expiresInStr = params.get("expires_in");

    if (!accessToken) {
      return null;
    }

    const expiresIn = parseInt(expiresInStr || "3600", 10);
    const expiresAt = Date.now() + expiresIn * 1000;

    return {
      accessToken,
      expiresIn,
      expiresAt,
    };
  } catch {
    return null;
  }
}
