"use client";

import Image from "next/image";
import type { SkinOffer, BundleOffer } from "@/lib/types";

interface ShopGridProps {
  skins: SkinOffer[];
  bundle: BundleOffer | null;
  skinMap: Map<string, { displayName: string; displayIcon: string }>;
  bundleMap: Map<string, { displayName: string; displayIcon: string }>;
}

export function ShopGrid({ skins, bundle, skinMap, bundleMap }: ShopGridProps) {
  return (
    <div className="space-y-6 fade-in">
      <div className="card-bg p-6">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
          Daily Offers
        </h3>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {skins.map((skin) => {
            const skinInfo = skinMap.get(skin.skinUuid);
            return (
              <div
                key={skin.offerId}
                className="card-bg overflow-hidden group cursor-pointer"
              >
                <div className="relative w-full aspect-[4/3] bg-[#0f0f1a]">
                  {skinInfo?.displayIcon || skin.skinImage ? (
                    <Image
                      src={skinInfo?.displayIcon || skin.skinImage}
                      alt={skinInfo?.displayName || skin.skinName}
                      fill
                      className="object-contain p-4 group-hover:scale-105 transition-transform duration-300"
                      unoptimized
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-gray-600 text-xs">
                      No image
                    </div>
                  )}
                  <div className="absolute top-2 right-2">
                    <span className="vp-badge">{skin.vpCost} VP</span>
                  </div>
                </div>
                <div className="p-3">
                  <p className="text-sm font-semibold text-white line-clamp-1">
                    {skinInfo?.displayName || skin.skinName}
                  </p>
                  {skin.weaponName && (
                    <p className="text-xs text-gray-500 mt-0.5">{skin.weaponName}</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {bundle && (
        <div className="card-bg p-6">
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-4">
            Bundle Offer
          </h3>
          <div className="relative w-full aspect-[16/6] bg-[#0f0f1a] rounded-xl overflow-hidden group cursor-pointer">
            {bundleMap.get(bundle.bundleUuid)?.displayIcon || bundle.bundleImage ? (
              <Image
                src={bundleMap.get(bundle.bundleUuid)?.displayIcon || bundle.bundleImage}
                alt={bundleMap.get(bundle.bundleUuid)?.displayName || bundle.bundleName}
                fill
                className="object-contain p-4 group-hover:scale-105 transition-transform duration-300"
                unoptimized
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-gray-600 text-sm">
                No bundle image
              </div>
            )}
            <div className="absolute bottom-3 right-3 flex items-center gap-3">
              <span className="vp-badge">{bundle.vpCost} VP</span>
            </div>
            <div className="absolute bottom-3 left-3">
              <p className="text-white font-bold text-lg">
                {bundleMap.get(bundle.bundleUuid)?.displayName || bundle.bundleName}
              </p>
            </div>
          </div>
        </div>
      )}

      {skins.length === 0 && !bundle && (
        <div className="card-bg p-12 text-center">
          <div className="text-4xl mb-4">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#ff4655" strokeWidth="1.5" className="mx-auto opacity-50">
              <path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z"/>
              <line x1="3" y1="6" x2="21" y2="6"/>
              <path d="M16 10a4 4 0 01-8 0"/>
            </svg>
          </div>
          <p className="text-gray-500">Shop data unavailable.</p>
        </div>
      )}
    </div>
  );
}
