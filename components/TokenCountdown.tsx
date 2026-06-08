"use client";

import { useEffect, useState } from "react";
import { formatTime } from "@/lib/utils";

interface TokenCountdownProps {
  expiresAt: number;
}

export function TokenCountdown({ expiresAt }: TokenCountdownProps) {
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [isExpired, setIsExpired] = useState(false);

  useEffect(() => {
    const tick = () => {
      const left = Math.max(0, Math.floor((expiresAt - Date.now()) / 1000));
      setSecondsLeft(left);
      if (left === 0) setIsExpired(true);
    };

    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [expiresAt]);

  const hours = Math.floor(secondsLeft / 3600);
  const minutes = Math.floor((secondsLeft % 3600) / 60);
  const secs = secondsLeft % 60;

  if (isExpired) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 bg-red-500/10 border border-red-500/30 rounded-lg">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ff4655" strokeWidth="2">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
        </svg>
        <span className="text-red-400 text-xs font-medium">Token đã hết hạn</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-[#1a1a2e] border border-[#2a2a3e] rounded-lg">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#00d4ff" strokeWidth="2">
        <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
      </svg>
      <span className="text-cyan text-xs font-mono font-medium">
        {hours > 0 ? `${hours}h ` : ""}{minutes.toString().padStart(2, "0")}:{secs.toString().padStart(2, "0")}
      </span>
      <span className="text-gray-500 text-xs">còn lại</span>
    </div>
  );
}
