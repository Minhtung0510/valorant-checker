"use client";

import { useState } from "react";
import { parseRedirectUrl } from "@/lib/parseRedirectUrl";
import type { Region } from "@/lib/types";

interface TokenInputProps {
  onTokenParsed: (accessToken: string, expiresIn: number) => void;
  isLoading: boolean;
}

export function TokenInput({ onTokenParsed, isLoading }: TokenInputProps) {
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [region, setRegion] = useState<Region>("AP");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!url.trim()) {
      setError("Vui lòng dán URL redirect từ trình duyệt.");
      return;
    }

    const parsed = parseRedirectUrl(url);
    if (!parsed) {
      setError(
        'URL không hợp lệ. Hãy đảm bảo bạn đã copy ĐẦY ĐỦ URL từ thanh địa chỉ, bao gồm phần # access_token.'
      );
      return;
    }

    // Validate token looks like JWT
    if (!parsed.accessToken.startsWith("eyJ")) {
      setError("access_token không đúng định dạng JWT. Hãy copy lại URL.");
      return;
    }

    setSuccess(`Token hợp lệ! Token dài ${parsed.accessToken.length} ký tự. Đang xử lý...`);
    onTokenParsed(parsed.accessToken, parsed.expiresIn);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Dán URL redirect từ Riot
          </label>
          <textarea
            className="input-field resize-none font-mono text-xs h-28"
            placeholder={`http://localhost:3001/redirect#access_token=eyJ...&expires_in=3600`}
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              setError("");
              setSuccess("");
            }}
            disabled={isLoading}
          />
          {url && (
            <p className="text-xs text-gray-600 mt-1">
              URL dài: {url.length} ký tự
              {url.includes("access_token=") ? " ✓ Có access_token" : " ✗ Không có access_token"}
            </p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Chọn Region
          </label>
          <div className="flex gap-3 flex-wrap">
            {(["AP", "NA", "EU", "KR"] as Region[]).map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => setRegion(r)}
                disabled={isLoading}
                className={`region-badge transition-all ${
                  region === r
                    ? r === "AP"
                      ? "region-ap bg-[rgba(255,100,50,0.3)]"
                      : r === "NA"
                      ? "region-na bg-[rgba(0,150,255,0.3)]"
                      : r === "EU"
                      ? "region-eu bg-[rgba(0,200,100,0.3)]"
                      : "region-kr bg-[rgba(200,100,255,0.3)]"
                    : "bg-[#1a1a2e] text-gray-500 border-[#2a2a3e]"
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/40 rounded-lg px-4 py-3 text-red-400 text-sm flex items-start gap-2">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="flex-shrink-0 mt-0.5">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            {error}
          </div>
        )}

        {success && !isLoading && (
          <div className="bg-green-500/10 border border-green-500/40 rounded-lg px-4 py-3 text-green-400 text-sm flex items-start gap-2">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="flex-shrink-0 mt-0.5">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            {success}
          </div>
        )}

        <button
          type="submit"
          className="btn-primary w-full text-center"
          disabled={isLoading || !url.trim()}
        >
          {isLoading ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
              </svg>
              Đang xử lý...
            </span>
          ) : (
            "Tiến hành Check"
          )}
        </button>

        <p className="text-center text-gray-600 text-xs">
          Token chỉ được dùng trong phiên này, không được lưu trữ bất kỳ đâu.
        </p>
      </form>
  );
}
