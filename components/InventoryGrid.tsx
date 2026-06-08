"use client";

import { useState, useMemo } from "react";
import Image from "next/image";
import type { InventoryItem, InventoryTab, SkinFilter } from "@/lib/types";

interface InventoryGridProps {
  skins: InventoryItem[];
  buddies: InventoryItem[];
  agents: InventoryItem[];
  cards: InventoryItem[];
  sprays: InventoryItem[];
  weaponMap: Map<string, string>;
  agentMap: Map<string, { displayName: string; displayIcon: string }>;
  sprayMap: Map<string, { displayName: string; displayIcon: string }>;
  cardMap: Map<string, { displayName: string; displayIcon: string }>;
  buddyMap: Map<string, { displayName: string; displayIcon: string }>;
}

const WEAPON_FILTERS: { label: string; value: SkinFilter }[] = [
  { label: "All", value: "all" },
  { label: "Vandal", value: "vandal" },
  { label: "Phantom", value: "phantom" },
  { label: "Operator", value: "operator" },
  { label: "Sheriff", value: "sheriff" },
  { label: "Ghost", value: "ghost" },
  { label: "Classic", value: "classic" },
  { label: "Melee", value: "melee" },
  { label: "Shorty", value: "shorty" },
  { label: "Bulldog", value: "bulldog" },
  { label: "Guardian", value: "guardian" },
  { label: "Ares", value: "ares" },
  { label: "Odin", value: "odin" },
  { label: "Knife", value: "knife" },
];

const WEAPON_NORMALIZED: Record<string, string> = {
  vandal: "vandal",
  phantom: "phantom",
  operator: "operator",
  sheriff: "sheriff",
  ghost: "ghost",
  classic: "classic",
  melee: "melee",
  shorty: "shorty",
  bulldog: "bulldog",
  guardian: "guardian",
  ares: "ares",
  odin: "odin",
  "tactical knife": "knife",
  knife: "knife",
};

export function InventoryGrid({
  skins,
  buddies,
  agents,
  cards,
  sprays,
  weaponMap,
  agentMap,
  sprayMap,
  cardMap,
  buddyMap,
}: InventoryGridProps) {
  const [activeTab, setActiveTab] = useState<InventoryTab>("skins");
  const [skinFilter, setSkinFilter] = useState<SkinFilter>("all");

  const filteredSkins = useMemo(() => {
    if (skinFilter === "all") return skins;
    return skins.filter((skin) => {
      const weaponName = weaponMap.get(skin.itemUuid)?.toLowerCase() ?? "";
      const normalized = WEAPON_NORMALIZED[weaponName] ?? weaponName;
      return normalized === skinFilter;
    });
  }, [skins, skinFilter, weaponMap]);

  const TABS: { key: InventoryTab; label: string; count: number }[] = [
    { key: "skins", label: "Skins", count: skins.length },
    { key: "buddies", label: "Buddies", count: buddies.length },
    { key: "agents", label: "Agents", count: agents.length },
    { key: "cards", label: "Cards", count: cards.length },
    { key: "sprays", label: "Sprays", count: sprays.length },
  ];

  const renderSkinGrid = () => (
    <div>
      <div className="flex flex-wrap gap-2 mb-4">
        {WEAPON_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setSkinFilter(f.value)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-all ${
              skinFilter === f.value
                ? "bg-accent border-accent text-white"
                : "bg-[#0f0f1a] border-[#2a2a3e] text-gray-400 hover:border-accent/50"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>
      {filteredSkins.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <p>No skins found for this filter.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {filteredSkins.map((item) => (
            <div
              key={item.itemUuid}
              className="card-bg p-3 flex flex-col items-center gap-2 group cursor-pointer"
            >
              <div className="relative w-full aspect-[4/3] bg-[#0f0f1a] rounded-lg overflow-hidden">
                {item.image ? (
                  <Image
                    src={item.image}
                    alt={item.name}
                    fill
                    className="object-contain p-2 group-hover:scale-105 transition-transform"
                    unoptimized
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-gray-600 text-xs">
                    No image
                  </div>
                )}
              </div>
              <p className="text-xs text-center text-white font-medium leading-tight line-clamp-2 w-full">
                {item.name}
              </p>
              {item.weaponName && (
                <span className="text-[10px] text-cyan bg-[#0f0f1a] px-2 py-0.5 rounded-full">
                  {item.weaponName}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const renderGenericGrid = <T extends InventoryItem>(
    items: T[],
    getName: (item: T, map: typeof agentMap) => string,
    getImage: (item: T, map: typeof agentMap) => string
  ) => (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
      {items.map((item) => (
        <div
          key={item.itemUuid}
          className="card-bg p-3 flex flex-col items-center gap-2 group cursor-pointer"
        >
          <div className="relative w-full aspect-square bg-[#0f0f1a] rounded-lg overflow-hidden">
            {getImage(item, agentMap) ? (
              <Image
                src={getImage(item, agentMap)}
                alt={getName(item, agentMap)}
                fill
                className="object-contain p-2 group-hover:scale-105 transition-transform"
                unoptimized
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-gray-600 text-xs">
                No image
              </div>
            )}
          </div>
          <p className="text-xs text-center text-white font-medium leading-tight line-clamp-2 w-full">
            {getName(item, agentMap)}
          </p>
        </div>
      ))}
    </div>
  );

  const renderContent = () => {
    switch (activeTab) {
      case "skins":
        return renderSkinGrid();
      case "buddies":
        return renderGenericGrid(
          buddies,
          (item) => buddyMap.get(item.itemUuid)?.displayName ?? item.name,
          (item) => buddyMap.get(item.itemUuid)?.displayIcon ?? item.image
        );
      case "agents":
        return renderGenericGrid(
          agents,
          (item) => agentMap.get(item.itemUuid)?.displayName ?? item.name,
          (item) => agentMap.get(item.itemUuid)?.displayIcon ?? item.image
        );
      case "cards":
        return renderGenericGrid(
          cards,
          (item) => cardMap.get(item.itemUuid)?.displayName ?? item.name,
          (item) => cardMap.get(item.itemUuid)?.displayIcon ?? item.image
        );
      case "sprays":
        return renderGenericGrid(
          sprays,
          (item) => sprayMap.get(item.itemUuid)?.displayName ?? item.name,
          (item) => sprayMap.get(item.itemUuid)?.displayIcon ?? item.image
        );
    }
  };

  return (
    <div className="card-bg p-6 fade-in">
      <div className="flex items-center gap-1 border-b border-[#2a2a3e] mb-6 -mx-6 px-6">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-3 text-sm font-semibold transition-all relative ${
              activeTab === tab.key ? "text-accent" : "text-gray-500 hover:text-white"
            }`}
          >
            {tab.label}
            <span className={`ml-1.5 text-xs px-1.5 py-0.5 rounded-full ${
              activeTab === tab.key ? "bg-accent/20 text-accent" : "bg-[#2a2a3e] text-gray-500"
            }`}>
              {tab.count}
            </span>
            {activeTab === tab.key && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent" />
            )}
          </button>
        ))}
      </div>
      {renderContent()}
    </div>
  );
}
