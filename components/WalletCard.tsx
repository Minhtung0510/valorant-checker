"use client";

import { formatVP } from "@/lib/utils";

interface WalletCardProps {
  vp: number;
  rp: number;
  kingdomCredits: number;
}

export function WalletCard({ vp, rp, kingdomCredits }: WalletCardProps) {
  return (
    <div className="card-bg p-6 fade-in">
      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
        Ví
      </h3>
      <div className="space-y-3">
        <div className="flex items-center justify-between bg-[#0f0f1a] rounded-lg p-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-md bg-gradient-to-br from-[#7b2d8b] to-[#e040fb] flex items-center justify-center">
              <span className="text-xs font-bold">VP</span>
            </div>
            <span className="text-sm text-gray-400">Valorant Points</span>
          </div>
          <span className="text-lg font-bold text-white">{formatVP(vp)}</span>
        </div>

        <div className="flex items-center justify-between bg-[#0f0f1a] rounded-lg p-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-md bg-gradient-to-br from-[#00d4aa] to-[#00a8cc] flex items-center justify-center">
              <span className="text-xs font-bold text-black">RP</span>
            </div>
            <span className="text-sm text-gray-400">Radianite Points</span>
          </div>
          <span className="text-lg font-bold text-white">{formatVP(rp)}</span>
        </div>

        <div className="flex items-center justify-between bg-[#0f0f1a] rounded-lg p-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-md bg-gradient-to-br from-[#ffd700] to-[#ff8c00] flex items-center justify-center">
              <span className="text-xs font-bold text-black">KC</span>
            </div>
            <span className="text-sm text-gray-400">Kingdom Credits</span>
          </div>
          <span className="text-lg font-bold text-white">{formatVP(kingdomCredits)}</span>
        </div>
      </div>
    </div>
  );
}
