/** Sortable table with detailed volume statistics per stock. */

import { useState } from "react";
import type { SessionStats } from "../../types";
import { formatVolume, formatVnd } from "../../utils/format-number";

interface VolumeDetailTableProps {
  stats: SessionStats[];
}

type SortKey = "symbol" | "buy_vol" | "sell_vol" | "total_vol" | "buy_ratio";
type SortDir = "asc" | "desc";

export function VolumeDetailTable({ stats }: VolumeDetailTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("total_vol");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const sortedStats = [...stats].sort((a, b) => {
    let aVal: number | string;
    let bVal: number | string;

    switch (sortKey) {
      case "symbol":
        aVal = a.symbol;
        bVal = b.symbol;
        break;
      case "buy_vol":
        aVal = a.mua_chu_dong_volume;
        bVal = b.mua_chu_dong_volume;
        break;
      case "sell_vol":
        aVal = a.ban_chu_dong_volume;
        bVal = b.ban_chu_dong_volume;
        break;
      case "total_vol":
        aVal = a.total_volume;
        bVal = b.total_volume;
        break;
      case "buy_ratio":
        aVal = a.total_volume > 0 ? (a.mua_chu_dong_volume / a.total_volume) * 100 : 0;
        bVal = b.total_volume > 0 ? (b.mua_chu_dong_volume / b.total_volume) * 100 : 0;
        break;
    }

    if (aVal < bVal) return sortDir === "asc" ? -1 : 1;
    if (aVal > bVal) return sortDir === "asc" ? 1 : -1;
    return 0;
  });

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-gray-800">
          <tr>
            <th onClick={() => handleSort("symbol")} className="px-4 py-3 text-left cursor-pointer hover:bg-gray-700">
              Symbol {sortKey === "symbol" && (sortDir === "asc" ? "↑" : "↓")}
            </th>
            <th onClick={() => handleSort("buy_vol")} className="px-4 py-3 text-right cursor-pointer hover:bg-gray-700">
              Buy Vol {sortKey === "buy_vol" && (sortDir === "asc" ? "↑" : "↓")}
            </th>
            <th className="px-4 py-3 text-right">Buy Value</th>
            <th onClick={() => handleSort("sell_vol")} className="px-4 py-3 text-right cursor-pointer hover:bg-gray-700">
              Sell Vol {sortKey === "sell_vol" && (sortDir === "asc" ? "↑" : "↓")}
            </th>
            <th className="px-4 py-3 text-right">Sell Value</th>
            <th className="px-4 py-3 text-right">Neutral</th>
            <th onClick={() => handleSort("total_vol")} className="px-4 py-3 text-right cursor-pointer hover:bg-gray-700">
              Total {sortKey === "total_vol" && (sortDir === "asc" ? "↑" : "↓")}
            </th>
            <th onClick={() => handleSort("buy_ratio")} className="px-4 py-3 text-right cursor-pointer hover:bg-gray-700">
              Buy Ratio {sortKey === "buy_ratio" && (sortDir === "asc" ? "↑" : "↓")}
            </th>
          </tr>
        </thead>
        <tbody>
          {sortedStats.map((stat) => {
            const buyRatio = stat.total_volume > 0 ? (stat.mua_chu_dong_volume / stat.total_volume) * 100 : 0;
            const rowBg = buyRatio > 60 ? "bg-red-900/20" : buyRatio < 40 ? "bg-green-900/20" : "";

            return (
              <tr key={stat.symbol} className={`border-t border-gray-800 hover:bg-gray-800/50 ${rowBg}`}>
                <td className="px-4 py-2 font-semibold">{stat.symbol}</td>
                <td className="px-4 py-2 text-right text-red-400">{formatVolume(stat.mua_chu_dong_volume)}</td>
                <td className="px-4 py-2 text-right">{formatVnd(stat.mua_chu_dong_value)}</td>
                <td className="px-4 py-2 text-right text-green-400">{formatVolume(stat.ban_chu_dong_volume)}</td>
                <td className="px-4 py-2 text-right">{formatVnd(stat.ban_chu_dong_value)}</td>
                <td className="px-4 py-2 text-right text-yellow-400">{formatVolume(stat.neutral_volume)}</td>
                <td className="px-4 py-2 text-right">{formatVolume(stat.total_volume)}</td>
                <td className="px-4 py-2 text-right font-semibold">{buyRatio.toFixed(1)}%</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
