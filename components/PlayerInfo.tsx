"use client";

import Link from "next/link";
import Image from "next/image";
import { TokenCountdown } from "./TokenCountdown";
import type { Region } from "@/lib/types";

interface PlayerInfoProps {
  gameName: string;
  tagLine: string;
  puuid: string;
  region: Region;
  expiresAt: number;
  level?: number;
}

const REGION_LABELS: Record<Region, string> = {
  AP: "Asia Pacific",
  NA: "North America",
  EU: "Europe",
  KR: "Korea",
};

export function PlayerInfo({ gameName, tagLine, region, expiresAt, level }: PlayerInfoProps) {
  return (
    <div className="card-bg p-6 fade-in">
      <div className="flex items-start justify-between mb-6">
        <div className="flex items-center gap-4">
          <div className="relative">
            <div className="w-20 h-20 rounded-xl bg-gradient-to-br from-[#ff4655] to-[#cc3444] flex items-center justify-center text-white font-bold text-2xl">
              {gameName.charAt(0).toUpperCase()}
            </div>
            {level !== undefined && (
              <div className="absolute -bottom-2 -right-2 bg-[#1a1a2e] border border-[#2a2a3e] rounded-full px-2 py-0.5 text-xs font-bold text-cyan">
                {level}
              </div>
            )}
          </div>
          <div>
            <h2 className="text-2xl font-bold text-white">
              {gameName}
              <span className="text-gray-500">#{tagLine}</span>
            </h2>
            <div className="flex items-center gap-2 mt-1">
              <span
                className={`region-badge ${
                  region === "AP"
                    ? "region-ap"
                    : region === "NA"
                    ? "region-na"
                    : region === "EU"
                    ? "region-eu"
                    : "region-kr"
                }`}
              >
                {region}
              </span>
              <span className="text-gray-500 text-xs">{REGION_LABELS[region]}</span>
            </div>
          </div>
        </div>

        <div className="flex flex-col items-end gap-2">
          <TokenCountdown expiresAt={expiresAt} />
          <Link href="/" className="btn-secondary text-xs px-3 py-1.5">
            Cập nhật token
          </Link>
        </div>
      </div>

      <div className="h-px bg-[#2a2a3e]" />
    </div>
  );
}
