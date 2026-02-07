/** Summary KPI cards for buy/sell/neutral volume ratios. */

import type { SessionStats } from "../../types";

interface VolumeRatioSummaryCardsProps {
  stats: SessionStats[];
}

export function VolumeRatioSummaryCards({ stats }: VolumeRatioSummaryCardsProps) {
  // Aggregate stats
  const totalBuy = stats.reduce((sum, s) => sum + s.mua_chu_dong_volume, 0);
  const totalSell = stats.reduce((sum, s) => sum + s.ban_chu_dong_volume, 0);
  const totalVolume = stats.reduce((sum, s) => sum + s.total_volume, 0);

  const buyRatio = totalVolume > 0 ? (totalBuy / totalVolume) * 100 : 0;
  const sellRatio = totalVolume > 0 ? (totalSell / totalVolume) * 100 : 0;
  const neutralRatio = 100 - buyRatio - sellRatio;

  const cards = [
    { label: "Buy Ratio", value: buyRatio, colorClass: "text-red-400" },
    { label: "Sell Ratio", value: sellRatio, colorClass: "text-green-400" },
    { label: "Neutral", value: neutralRatio, colorClass: "text-yellow-400" },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col items-center justify-center"
        >
          <div className={`text-2xl font-bold ${card.colorClass}`}>
            {card.value.toFixed(1)}%
          </div>
          <div className="text-xs text-gray-400 mt-1">{card.label}</div>
        </div>
      ))}
    </div>
  );
}
