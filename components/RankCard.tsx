"use client";

import Image from "next/image";

interface RankTier {
  tier: number;
  tierName: string;
  smallIcon: string;
  largeIcon: string;
}

interface RankCardProps {
  rankData: {
    currentRank: {
      tier: number;
      division: number;
      rr: number;
      name: string;
      icon: string;
    };
    peakRank: {
      tier: number;
      name: string;
      icon: string;
      act: string;
    };
    seasonInfo: string;
    peakHistory: Array<{
      tier: number;
      name: string;
      icon: string;
      act: string;
    }>;
  };
  rankTiers: RankTier[];
}

const RANK_COLORS: Record<string, string> = {
  Iron: "#4a4a4a",
  Bronze: "#cd7f32",
  Silver: "#c0c0c0",
  Gold: "#ffd700",
  Platinum: "#00d4aa",
  Diamond: "#b9f2ff",
  Ascendant: "#00ff88",
  Immortal: "#ff4554",
  Radiant: "#ffe55c",
  "Iron 1": "#4a4a4a",
  "Bronze 1": "#cd7f32",
  "Silver 1": "#c0c0c0",
  "Gold 1": "#ffd700",
  "Platinum 1": "#00d4aa",
  "Diamond 1": "#b9f2ff",
  "Ascendant 1": "#00ff88",
  "Immortal 1": "#ff4554",
};

const DIVISION_LABELS = ["I", "II", "III"];

export function RankCard({ rankData, rankTiers }: RankCardProps) {
  const { currentRank, peakRank, peakHistory } = rankData;

  const currentTierInfo = rankTiers.find((t) => t.tier === currentRank.tier);
  const peakTierInfo = rankTiers.find((t) => t.tier === peakRank.tier);

  const rankColor = RANK_COLORS[currentRank.name] ?? "#888";

  return (
    <div className="card-bg p-6 fade-in">
      <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
        Xếp hạng
      </h3>

      <div className="flex items-center gap-6 mb-6">
        <div className="relative">
          <div
            className="w-24 h-24 rounded-xl flex items-center justify-center"
            style={{
              background: `linear-gradient(135deg, ${rankColor}33, ${rankColor}11)`,
              border: `2px solid ${rankColor}66`,
            }}
          >
            {currentTierInfo?.largeIcon ? (
              <Image
                src={currentTierInfo.largeIcon}
                alt={currentRank.name}
                width={80}
                height={80}
                className="object-contain"
                unoptimized
              />
            ) : currentRank.icon ? (
              <Image
                src={currentRank.icon}
                alt={currentRank.name}
                width={80}
                height={80}
                className="object-contain"
                unoptimized
              />
            ) : (
              <span className="text-3xl font-bold" style={{ color: rankColor }}>
                {currentRank.tier}
              </span>
            )}
          </div>
        </div>

        <div>
          <p className="text-2xl font-bold text-white">{currentRank.name}</p>
          {currentRank.division > 0 && (
            <p className="text-gray-400 text-sm">
              {DIVISION_LABELS[currentRank.division - 1] ?? ""}
            </p>
          )}
          <div className="flex items-center gap-2 mt-2">
            <div className="w-32 h-2 bg-[#0f0f1a] rounded-full overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${Math.min(100, (currentRank.rr / 100) * 100)}%`,
                  background: `linear-gradient(90deg, ${rankColor}, ${rankColor}cc)`,
                }}
              />
            </div>
            <span className="text-xs font-mono text-gray-400">{currentRank.rr} RR</span>
          </div>
        </div>
      </div>

      {peakRank.tier > 0 && (
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="bg-[#0f0f1a] rounded-lg p-3 flex items-center gap-3">
            <span className="text-xs text-gray-500 uppercase">Peak</span>
            <span className="text-sm font-bold text-white">{peakRank.name}</span>
            {peakTierInfo?.smallIcon && (
              <Image
                src={peakTierInfo.smallIcon}
                alt={peakRank.name}
                width={20}
                height={20}
                className="object-contain"
                unoptimized
              />
            )}
          </div>
          <div className="bg-[#0f0f1a] rounded-lg p-3">
            <span className="text-xs text-gray-500 uppercase block">Season</span>
            <span className="text-sm font-bold text-white">{peakRank.act}</span>
          </div>
        </div>
      )}

      {peakHistory.length > 0 && (
        <div>
          <p className="text-xs text-gray-500 uppercase mb-2">Lịch sử peak rank</p>
          <div className="space-y-2">
            {peakHistory.slice(0, 3).map((peak, i) => {
              const tierInfo = rankTiers.find((t) => t.tier === peak.tier);
              return (
                <div key={i} className="flex items-center justify-between bg-[#0f0f1a] rounded-lg px-3 py-2">
                  <div className="flex items-center gap-2">
                    {tierInfo?.smallIcon && (
                      <Image
                        src={tierInfo.smallIcon}
                        alt={peak.name}
                        width={18}
                        height={18}
                        className="object-contain"
                        unoptimized
                      />
                    )}
                    <span className="text-sm text-white">{peak.name}</span>
                  </div>
                  <span className="text-xs text-gray-500">{peak.act}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
